import os

#日志配置
log_dir = "logs"# 日志路径
log_name = "app.log" #日志名
log_backup_num = 14 #最多备份数

#服务器开放端口配置
HOST = "127.0.0.1"
PORT = 8000

#报警接收
RECEIVE_URL = "http://10.120.24.109:8082/admin/ai/iotAiAlarmRecord/recieveAiAlarmData"

#minio配置
bucketName = "application" #minio桶名
endpoint="10.120.24.109:19000"
access_key="admin"
secret_key="admin123456"
headers = {
            "Authorization": "aaab26be-c720-44e0-b10a-73948a3ec247"
}

#检测配置
DETECT_INTERVAL = 20 #每隔多少帧抽一帧
SAVE_LENGTH = 3 #保存报警帧前后多少秒
ROOT_PATH = os.getcwd() #项目根目录..\detect\
#！！！！
#如果是pycharm环境请用os.path.dirname(os.getcwd())

TEMP_FILE = rf"{ROOT_PATH}\tempfiles"   #结果文件临时储存地址
TEMP_VIDEO = rf"{TEMP_FILE}\temp_video.mp4" #视频本地临时储存地址

if_divide:bool  =  True #是否进行图片分割检测,大幅提升检测小物体的精度，但指数提升检测消耗
divide_row = 2  #分割多少
divide_col  = 2

if_send_alarm:bool = False #是否发送报警
send_timeout = 5 #报警超时

if_multithread:bool = True #是否多线程处理
max_threads= int(os.cpu_count()*0.9)  # 最大同时处理任务数

#是否删除本地处理结果
if_delete_image_pre:bool = False #是否删除处理前图片
if_delete_image_post:bool = False #是否删除处理后图片
if_delete_video_clip:bool = False #是否删除截取视频