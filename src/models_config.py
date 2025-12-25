import os
from ultralytics import YOLO
from config import ROOT_PATH


"""
    模型配置界面
"""


MODELS_PATH_BY_NAME = {#模型名称转地址
    'wreckage' : f"{ROOT_PATH}\\models\\liefeng.pt",
    'person' : f'{ROOT_PATH}\\models\\human.pt',
    'tree' : f'',
    'floating' : f'{ROOT_PATH}\\models\\floating_detect_v2.pt',
    'gate' : f'',
}

MODELS_LABELS_BY_NAME = {#模型需要检测类型
    'wreckage' : [0],#['裂缝']
    'person' : [0],#person
    'tree' : [],
    'floating' : [0,1], #["植物"，“垃圾“]
    'gate' : [],
}

# model = YOLO(MODELS_PATH_BY_NAME["liefeng"])
# print(model.names)