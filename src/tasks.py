import collections
import os
import time
import uuid
from pathlib import Path

import numpy as np
import requests
from fastapi.encoders import jsonable_encoder
from minio.error import S3Error
from ultralytics import YOLO
import cv2
from logger import log
import models_config
import minio_config
import posts_config as post
import base64
import workers
import psutil
import GPUtil
import shutil
import config


"""
    任务处理方法
"""


DETECT_INTERVAL = config.DETECT_INTERVAL #每隔多少帧抽一帧
SAVE_LENGTH = config.SAVE_LENGTH #保存报警帧前后多少秒
ROOT_PATH = config.ROOT_PATH
TEMP_FILE = config.TEMP_FILE
TEMP_VIDEO = config.TEMP_VIDEO #视频本地临时储存地址


class Task:
    def __init__(self,  detect_id:int,stream:str,model : str,time : int,detect_interval:int=DETECT_INTERVAL,save_length:int=SAVE_LENGTH):
        # 任务信息
        self.detect_id =detect_id
        self.stream = stream
        self.model = model

        #任务处理要求
        self.last_sent_time=0
        self.detect_interval=detect_interval
        self.detect_cooldown=time
        self.save_length=save_length

        # 每次产生报警需要存的信息
        self.alarm_type = None
        self.frame_pre = None
        self.frame_post = None
        self.video_clip = None

    def download_if_needed(self,url:str):
        #判断是收到的是视频下载地址，视频流还是本地视频
        stream_keywords = ['hls', 'rtmp', 'm3u8', 'stream', 'live']
        if os.path.isfile(url):
            return url  #本地视频直接使用
        if any(keyword in url.lower() for keyword in stream_keywords):
            return url #视频流直接使用
        else:
            try:
                response = requests.get(url, stream=True)
                with open(TEMP_VIDEO, 'wb') as file:
                    for chunk in response.iter_content(chunk_size=8192):
                        file.write(chunk)
                return TEMP_VIDEO#视频下载地址下载后使用
            except Exception as e:
                log.error(f"cannot download video from {url},error:{e}")
                print(f"cannot download video from {url},error: {e}")
                return None

    def detect(self,frame,model:str):
        #进行yolo检测
        try:
            results = YOLO(models_config.MODELS_PATH_BY_NAME[model]).predict(
                source=frame,
                classes = models_config.MODELS_LABELS_BY_NAME[model],
                save=False,
                show=False,
                save_txt=False,
                verbose=False,
            )
            for result in results:
                for box in result.boxes:
                    if int(box.cls[0]) in models_config.MODELS_LABELS_BY_NAME[model]:
                        return result
        except Exception as e:
            log.critical(f"{e}")
            print(f"unprocessable entity,error:{e}")
        return None

    def grid_detect(self,frame, model:str, m=2, n=2):
        """
        分割检测，可以提升图像距离太远时的检测精度
        """
        h, w = frame.shape[:2]
        blocks = []
        try:
            yolo = YOLO(f"{models_config.MODELS_PATH_BY_NAME[model]}")
        except Exception as e:
            log.error(f".pt file do not exist:\nerror:{e}")
            print(f".pt file do not exist:\nerror:{e}")
            return None
        detected = False
        try:
            for i in range(m):
                row_blocks = []
                for j in range(n):
                    # 计算块边界
                    y1, y2 = i * h // m, (i + 1) * h // m if i < m - 1 else h
                    x1, x2 = j * w // n, (j + 1) * w // n if j < n - 1 else w
                    # 提取并检测块
                    block = frame[y1:y2, x1:x2]
                    result = yolo(block, verbose=False, show=False,classes = models_config.MODELS_LABELS_BY_NAME[model])[0]
                    if len(result) > 0:
                        detected = True
                    annotated = result.plot()
                    row_blocks.append(annotated)
                blocks.append(np.hstack(row_blocks))
            if detected:
                return [np.vstack(blocks)]
            else:
                return None
        except Exception as e:
            print(e)
            return None

    # def image_to_minio(self,file):
    #     # 没用上的minio发送
    #     found = minio_config.minio_client.bucket_exists(minio_config.bucketName)
    #     if not found:
    #         minio_config.minio_client.make_bucket(minio_config.bucketName)
    #     local_file_path = file  # 本地图片路径
    #     object_name =f"image/IotVideo/videoUrl/{str(uuid.uuid4())}.jpg"  # 图片在MinIO存储桶中的路径和名称
    #     try:
    #         minio_config.minio_client.fput_object(minio_config.bucketName, object_name, local_file_path)
    #         return object_name
    #     except S3Error as exc:
    #         log.critical(f"upload failed:\n\tdescription{exc}")
    #         print("upload failed:\n\tdescription:", exc)
    #         return None

    def image_to_base64(self,image):
        #图片转base64\
        if os.path.exists(image):
            with open(image, "rb") as image_file:
                return base64.b64encode(image_file.read()).decode('utf-8')
        else:
            return None

    def send_response(self):
        #发送报警
        try:
            response = post.response_alarm(
                base64Img = self.image_to_base64(self.frame_pre),
                base64ImgBox = self.image_to_base64(self.frame_post),
                alarmInfo = self.alarm_type,
                alarmTime = time.strftime("%Y%m%d%H%M%S"),
                detectId = self.detect_id
            )
            res = post.resonse_alarm(iotAiAlarmRecordDto=response)#表单数据

            if self.video_clip is not None:
                files = {'videoClip': (self.video_clip, open(self.video_clip, 'rb'), 'video/mp4')}#视频文件数据
            else:
                files = None
        except Exception as e:
            log.error(f"unable to generate response:\n{e}")
            print(f"unable to generate response:\n{e}")
            return

        try:
            #尝试发送
            requests.post(post.RECEIVE_URL, json=jsonable_encoder(res), files = files,headers=minio_config.headers,timeout=config.send_timeout)
            log.info("send alarm successfully")
            print(f"send alarm successfully")
        except Exception as e:
            log.critical(f"cannot send alarm：\n\taddress:{post.RECEIVE_URL}\n\terror:{e}")
            print(f"cannot send alarm：\n\taddress:{post.RECEIVE_URL}\n\terror:{e}")



    def process(self):
        #检测任务处理
        """
            1：
                获得文件来源时判断是下载链接，视频流，还是本地视频
            2：
                对图片直接进行检测，只可能有一次报警
                对视频抽帧进行视觉检测，抽帧有间隔，检测到报警后有冷却时间，此段时间内不检测
            3：
                检测到报警时保存报警帧，待框报警帧，报警帧前后视频片段，报警帧画框位置
            4：
                把报警信息打包成json对象进行发送

        """

        alarm_count=0
        total_frames=0
        stream = self.download_if_needed(self.stream)#判断一下地址类型，变为可以直接opencv处理的类型
        if not stream:
            return

        # 如果是图片直接检测走完
        try:
            pics = ['jpg', 'png', 'jpeg']
            if any(pic in self.stream.lower() for pic in pics):
                frame =cv2.imread(stream)

                if config.if_divide:#是否进行切割检测
                    result = self.grid_detect(frame, self.model)
                else:
                    result = self.detect(frame,self.model)

                if result:
                    #生成报警信息
                    self.alarm_type = self.model
                    uid = int(uuid.uuid4())

                    path_pre = f"{TEMP_FILE}\\{self.detect_id}\\pre"  # 本地保存原图片
                    os.makedirs(path_pre, exist_ok=True)
                    self.frame_pre = os.path.join(path_pre,
                                                       f"{self.detect_id % 100000000}_{self.model[:6]}_{uid}_pre.jpg")
                    shutil.copy(stream, self.frame_pre)

                    path_post = f"{TEMP_FILE}\\{self.detect_id}\\post"  # 本地保存带算法框图片
                    os.makedirs(path_post, exist_ok=True)
                    self.frame_post = os.path.join(path_post,
                                                        f"{self.detect_id % 100000000}_{self.model[:6]}_{uid}_post.jpg")
                    cv2.imwrite(self.frame_post, result[0])

                    #发送报警
                    if config.if_send_alarm:
                        self.send_response()

                    #记录报警触发日志
                    log.info(
                        f'alarm detected:\n\tdetect ID:{self.detect_id}\n\tstream:{self.stream}\n\talarm:{self.model}\tsaved to:{self.frame_post}')
                    print(
                        f"alarm detected：\tdetect ID:{self.detect_id % 1000000000}\tstream:{self.stream}\talarm:{self.model}\tsaved to:{self.frame_post}")
                return

        except Exception as e:
            log.error(f'processing image error:\n\tdetect id:{self.detect_id}\n\tstream:{self.stream}\n\terror:{str(e)}')
            print(f"processing image error:\n\tdetect id:{self.detect_id}\n\tstream:{self.stream}\n\terror:{str(e)}")

        #如果是视频则抽帧检测
        try:
            try:
                cap = cv2.VideoCapture(stream, cv2.CAP_FFMPEG)
            except Exception as e:
                log.critical(f"cannot open stream:{e}")
                print(f"cannot open stream:{e}")
                return
            if os.path.isfile(stream):#如果不是视频流，统计总帧数以查看处理进度
                total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            buffer_size = int(fps * self.save_length)  # 缓冲区，放前几秒的
            clip_frames = int(fps * self.save_length)  # 录取帧数，放后几秒的
            buffer = collections.deque(maxlen=buffer_size)
            last_trigger_frame = -self.detect_cooldown * fps# 上次报警时间，初始化为足够早的时间
            frame_count = 0
            recording = False
            recording_frames = 0
            out = None
            clip_count = 0

            while workers.statue_tasks[self.detect_id] > 0: # 以任务状态为标志位，正常情况是子任务数量，结束时自然减到0
                ret, frame = cap.read()
                if not ret:
                    break
                buffer.append((frame_count, frame.copy()))#总是将前save_length秒的帧记录下来
                if frame_count % self.detect_interval == 0 and frame_count - last_trigger_frame >= self.detect_cooldown * fps:  # 每隔开DETECT_INTERVAL抽1帧检测,且报警冷却已结束

                    # 是否进行分割检测
                    if config.if_divide:
                        result = self.grid_detect(frame, self.model)
                    else:
                        result = self.detect(frame,self.model)

                    if result:  # 如果监测有结果
                        alarm_count += 1
                        last_trigger_frame = frame_count
                        recording = True
                        recording_frames = 0
                        clip_count += 1
                        uid = int(uuid.uuid4())

                        # 保存要发送的内容
                        self.alarm_type = self.model

                        path_pre = f"{TEMP_FILE}\\{self.detect_id}\\pre"# 本地保存原图片
                        os.makedirs(path_pre, exist_ok=True)
                        self.frame_pre = os.path.join(path_pre,
                                                           f"{self.detect_id % 100000000}_{self.model[:6]}_{uid}_pre.jpg")
                        cv2.imwrite(self.frame_pre, frame)

                        path_post = f"{TEMP_FILE}\\{self.detect_id}\\post"# 本地保存带算法框图片
                        os.makedirs(path_post, exist_ok=True)
                        self.frame_post = os.path.join(path_post,
                                                            f"{self.detect_id % 100000000}_{self.model[:6]}_{uid}_post.jpg")
                        cv2.imwrite(self.frame_post, result[0])

                        path_clip = f"{TEMP_FILE}\\{self.detect_id}\\clip"# 本地保存视频片段
                        os.makedirs(path_clip, exist_ok=True)
                        self.video_clip = os.path.join(path_clip, f"{self.detect_id % 100000000}_{self.model[:6]}_{uid}_clip.mp4")
                        # 名字太长会报错
                        
                        #保存前save_length秒的视频内容，即触发报警前的几秒
                        try:
                            out = cv2.VideoWriter(
                                    self.video_clip,#视频文件名
                                    cv2.VideoWriter_fourcc(*'mp4v'),
                                    fps,
                                    (int(cap.get(3)), int(cap.get(4)))
                                ) 
                        except Exception as e:
                            log.error(f'video decoder error:\n\tdetect id:{self.detect_id}\n\tstream:{self.stream}\n\terror:{str(e)}')
                            print(f"video decoder error:\n\tdetect id:{self.detect_id}\n\tstream:{self.stream}\n\terror:{str(e)}")
                            return

                        # 把记录到的前save_length秒的帧组成视频
                        for idx, buffered_frame in buffer:
                            out.write(buffered_frame)

                        #记录日志
                        log.info(f'alarm detected:\n\tdetect ID:{self.detect_id}\n\tstream:{self.stream}\n\talarm count:{alarm_count}\n\talarm:{self.model}')
                        print(f"alarm detected：\tdetect ID:{self.detect_id%1000000000}\tstream:{self.stream}\talarm count:{alarm_count}\talarm:{self.model}")
                    elif not recording:
                        #print("no detection")
                        pass

                if recording:#找到后短时间不会监测但会把后save_length秒继续加到视频中，即触发报警后的几秒
                    out.write(frame)
                    recording_frames += 1
                    if recording_frames >= clip_frames:
                        # 如果已录制超过时长，结束录制获得完整视频
                        recording = False
                        out.release()
                        out = None
                        #所有报警信息都处理完毕，发送报警
                        if config.if_send_alarm:
                            self.send_response()

                frame_count += 1
                if total_frames != 0 and frame_count % self.detect_interval == 0:  # 如果不是视频流，则可以显示当前视频进度
                    percent = frame_count / total_frames
                    print(f"detect statue:{self.detect_id % 1000000000}\tstream:{self.stream[-15:]}\tmodel:{self.model}"
                          f"\t[{'█'*int(50*percent)+'-'*int(50*(1-percent))}]{percent*100:2.2f}%"
                          f"\tcpu_usage:{psutil.cpu_percent():2.2f}%\tmemory_usage:{psutil.virtual_memory().percent:2.2f}%"
                          f"\tgpu_usage:{GPUtil.getGPUs()[0].load*100:2.2f}%\tgpu_memory_usage:{GPUtil.getGPUs()[0].memoryUtil*100:2.2f}%")

            if out is not None:
                out.release()
            cap.release()

        except Exception as e:
            log.error(f'processing video error:\n\tdetect id:{self.detect_id}\n\tstream:{self.stream}\n\terror:{str(e)}')
            print(f"processing video error:\n\tdetect id:{self.detect_id}\n\tstream:{self.stream}\n\terror:{str(e)}")