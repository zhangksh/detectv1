import os
import shutil
import threading
from logger import log
from time import sleep, time
import config

"""
    任务接收和分发处理
"""

processing_tasks = {}#{detect_id3:task3,detect_id4:task4...}
statue_tasks = {}#{detect_id1:6,detect_id2:7...}
MAX_THREADS = config.max_threads #最大同时处理任务数


class task_processor:
    def __init__(self):
        self.threads_count = 0
        self.lock = threading.Lock()  # 添加锁确保线程安全
        self.thread = threading.Thread(target=self.distribute, daemon=True)
        self.thread.start()
        self.if_busy = False

    def distribute(self) -> None:
        #任务分发，将任务请求拆分成1个视频流对应1个模型的子任务，每个子任务单独分配进程
        while True:
            if processing_tasks:
                try:
                    task_id = next(iter(processing_tasks))
                    for task in processing_tasks[task_id]:
                        if (self.threads_count >= MAX_THREADS): #线程满了就等待
                            print(f"processor busy: {self.threads_count}/{MAX_THREADS}\twaiting tasks:{statue_tasks[task_id]}")
                            while self.threads_count >= MAX_THREADS:
                                sleep(1)
                        self.if_busy = False
                        processor = threading.Thread(#分配子任务线程并开始
                            target=self.processor,
                            args=(task,),
                            daemon=True
                        )
                        processor.start()
                    del processing_tasks[task_id]

                except StopIteration:
                    log.error("unable to distribute processor or task has bean deleted")
                    print("unable to distribute processor or task has bean deleted")

            elif self.threads_count == 0:#没有任务且没有在进行中的任务，就等待输入
                print("waiting for task...")
                sleep(4)
            sleep(1)

    def processor(self, task) -> None:
        #单个线程进行任务处理
        with self.lock:
            self.threads_count += 1
        print(f"start process:\n\ttask id:{task.detect_id}\n\tstream:{task.stream}\n\tmodel:{task.model}\n\tcpu_core_usage:{self.threads_count}/{MAX_THREADS}")
        log.info(f'start process:\n\ttask id:{task.detect_id}\n\tstream:{task.stream}\n\tmodel:{task.model}\n\tcpu_core_usage:{self.threads_count}/{MAX_THREADS}')
        start = time()

        task.process()

        if statue_tasks[task.detect_id] == 0:  # 正常情况下是自然减到0，直接置为0代表中止任务
            log.info(f"task abort:\n\tdetect_id:{task.detect_id}\n\tstream;{task.stream}\n\tmodel:{task.model}")
            print(f"task abort:\tdetect_id:{task.detect_id}\tstream;{task.stream}\tmodel:{task.model}")
        else:
            finished = time()
            statue_tasks[task.detect_id] -= 1
            print(f"task done:\ttask id:{task.detect_id}\tstream:{task.stream}\ttime:{finished - start:.2f}s\tsubstack remain:{statue_tasks[task.detect_id]}")
            log.info(f'task done:\n\ttask id:{task.detect_id}\n\tstream:{task.stream}\n\ttime_use:{finished - start:.2f}s')

        try:
            #是否删除本地处理结果
            if config.if_delete_image_pre:
                shutil.rmtree(f"{config.TEMP_FILE}\\{task.detect_id}\\pre")
            if config.if_delete_image_post:
                shutil.rmtree(f"{config.TEMP_FILE}\\{task.detect_id}\\post")
            if config.if_delete_video_clip:
                shutil.rmtree(f"{config.TEMP_FILE}\\{task.detect_id}\\clip")
        except Exception:
            pass

        with self.lock:#结束时使待处理子任务数量减1
            self.threads_count -= 1

