import os
import time
from datetime import datetime
from pathlib import Path
import pytz
import uvicorn
from fastapi import FastAPI
from logger import log
import posts_config as post
import workers
from tasks import Task
import models_config
import config


"""
    FASTAPI响应界面
"""
#默认运行端口
HOST = config.HOST
PORT = config.PORT
app=FastAPI()


"""
    接收开始检测请求端口
"""
@app.post("/api/v1/ai/startDetects")
async def startDetects(request: post.request_start):
    log.info(f"received startDetects request:\n {request}")
    print(f"received startDetects request: \n{request}")#消息已收到

    response = post.response_start(#编辑响应消息
        messageCode="ERROR",
        record=[]
    )

    missing_models = []#检查指定的模型是否存在
    for model in request.modelTypes:
        if model not in models_config.MODELS_PATH_BY_NAME:
            missing_models.append(model)
    if missing_models:
        log.info(f"required models do not exist\n\tmodel:{missing_models}")
        print(f"required models do not exist\n\tmodel:{missing_models}")
        return response

    try:#添加任务
        detect_id = time.time_ns()
        workers.processing_tasks[detect_id] = []  # 一个detect_id对应多个子任务
        workers.statue_tasks[detect_id] = 0#任务状态，数量为子任务数，为0则结束，查不到就是没添加

        # 支持的扩展名
        extends = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp',
                '.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.webm', '.mpeg', '.mpg'}

        for stream in request.listStreamings:
            for model in request.modelTypes:
                if os.path.isdir(stream):#如果给的目录，添加其下所有图片和视频为单独任务
                    for root, dirs, files in os.walk(stream):
                        for file in files:
                            if os.path.splitext(file)[1].lower() in extends:
                                path=os.path.abspath(os.path.join(root, file))
                                workers.statue_tasks[detect_id] += 1
                                workers.processing_tasks[detect_id].append(
                                    Task(
                                        detect_id = detect_id,
                                        stream = path,
                                        time = request.time,
                                        model = model
                                    )
                                )
                    continue
                else:#非目录
                    workers.statue_tasks[detect_id] += 1
                    workers.processing_tasks[detect_id].append(
                        Task(
                            detect_id=detect_id,
                            stream=stream,
                            time=request.time,
                            model=model
                        )
                    )

        for stream in request.listStreamings:
            response.record.append(post.Record(streaming=stream, detectId=detect_id))
        response.messageCode = "SUCCESS"
    except Exception as e:
        response.messageCode="ERROR"
        response.reason=[]

    log.info(f"startDetects response: \n\t{response}")
    print(f"startDetects response: \n\t{response}")
    return response


"""
    中止任务请求端口
"""
@app.post("/api/v1/ai/stopDetects")
async def stopDetects(request: post.request_stop):
    log.info(f"received stopDetects request:\n{request}")
    print(f"received stopDetects request: \n{request}")#消息已收到

    response = post.response_stop(#编辑响应消息
        messageCode="",
        messageInfo=""
    )
    if request.detectId in workers.statue_tasks:
        if workers.statue_tasks[request.detectId] == 0:
            response.messageCode="SUCCESS"
            response.messageInfo="detects already finished"
        else:
            workers.statue_tasks[int(request.detectId)]=0
            response.messageCode = "SUCCESS"
            response.messageInfo = f"stop detects successfully:{request.detectId}"
    else:
        response.messageCode = "ERROR"
        response.messageInfo = f"detect do not exist:{request.detectId}"

    log.info(f"stopDetects response: \n\t{response}")
    print(f"stopDetects response: \n\t{response}")

    return response

"""
    查询任务处理情况接口
"""
@app.post("/api/v1/ai/stateDetects")
async def stateDetects(request: post.request_state):
    log.info(f"received stateDetects request: \n{request}")
    print(f"received stateDetects request: \n{request}")#消息已收到

    response = post.response_state(#编辑响应消息
        messageCode=[]
    )
    for detect in request.detectId:
        response.messageCode.append(
            post.MessageCode(detectId = detect, state = detect in workers.statue_tasks))#等待或者在处理队伍里有就返回true
    log.info(f"stateDetects response: \n{response}")
    print(f"stateDetects response: \n{response}")
    return response


if __name__ == "__main__":
    log.info(f"----------------------------------------------------小模型处理任务开始----------------"
                            f"-------------------------------------\n\t北京时间：{datetime.now(pytz.timezone('Asia/Shanghai'))}"
                            f"\n\t开放端口：http://{HOST}:{PORT}")
    processor = workers.task_processor()#后台任务处理
    uvicorn.run(app=app,host=HOST,port=PORT)#开放端口

