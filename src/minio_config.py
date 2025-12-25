from minio import Minio
import config


"""
minio配置，当前未使用
"""
bucketName = config.bucketName #minio桶名
minio_client = Minio(
    endpoint=config.endpoint,  # MinIO服务器地址和端口
    access_key=config.access_key,   # 访问密钥
    secret_key=config.secret_key,   # 秘密密钥
    secure=False  # 设置为True如果使用HTTPS；False则使用HTTP[citation:7]
)

headers = config.headers

