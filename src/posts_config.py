from typing import List
from pydantic import BaseModel
import config

"""
    接口配置
"""


#"/api/v1/ai/startDetects"
class request_start(BaseModel):
    listStreamings : List[str]
    time : int
    modelTypes : List[str]

class Record(BaseModel):
    streaming : str
    detectId : int
class response_start(BaseModel):
    messageCode : str
    record : List[Record]

#"/api/v1/ai/stopDetects"
class request_stop(BaseModel):
    detectId : int

class response_stop(BaseModel):
    messageCode : str
    messageInfo : str

#"/api/v1/ai/stateDetects"
class request_state(BaseModel):
    detectId : List[int]

class MessageCode(BaseModel):
    detectId : int
    state : bool
class response_state(BaseModel):
    messageCode : List[MessageCode]

#send_response
RECEIVE_URL = config.RECEIVE_URL #接收处理完成数据的地址，"http://10.120.24.109:8082/admin/ai/iotAiAlarmRecord/recieveAiAlarmData"
class response_alarm(BaseModel):
    base64Img : str
    base64ImgBox : str
    alarmInfo : str
    alarmTime : str
    detectId : int
class resonse_alarm(BaseModel):
    iotAiAlarmRecordDto: response_alarm

