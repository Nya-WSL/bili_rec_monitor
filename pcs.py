import os
import sys
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)
from openapi_client.api import fileupload_api
import openapi_client
import hashlib
import logging
import shutil
import math

# LEVEL: DEBUG INFO WARNING ERROR CRITICAL
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s [%(levelname)s]: %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S'
                    )

"""
切分指定大小文件到指定路径
"""
def split(fromfile, todir, chunksize = 4*1024*1024):
    if not os.path.exists(todir):  # check whether todir exists or not
        os.makedirs(todir)
    else:
        for fname in os.listdir(todir):
            os.remove(os.path.join(todir, fname))
    paths = []
    partnum = 0
    inputfile = open(fromfile, 'rb')  # open the fromfile
    file_name = os.path.basename(fromfile)
    while True:
        chunk = inputfile.read(chunksize)
        if not chunk:  # check the chunk is empty
            break
        filename = os.path.join(todir, ('%s.part%04d' % (file_name, partnum)))
        paths.append(filename)
        fileobj = open(filename, 'wb')  # make partfile
        fileobj.write(chunk)  # write data into partfile
        fileobj.close()
        logging.info(f"Spliting: {filename}({partnum + 1}/{math.ceil(os.path.getsize(fromfile) / chunksize)})")
        partnum += 1
    return paths

"""
获取文件MD5值
"""
def get_file_md5(file_name):
    m = hashlib.md5()  # 创建md5对象
    with open(file_name, 'rb') as fobj:
        while True:
            data = fobj.read(4096)
            if not data:
                break
            m.update(data)  # 更新md5对象
    return m.hexdigest()  # 返回md5对象

"""
获取文件夹下文件MD5值
"""
def get_files_md5(dir_path):
    paths = []
    md5s = []
    for file_name in sorted(os.listdir(dir_path)):
        path = os.path.join(dir_path, file_name)
        if not os.path.isdir(path) and not file_name.startswith('.'):
            md5 = get_file_md5(path)
            paths.append(path)
            md5s.append(md5)
    return paths, md5s

"""
获取文件MD5值2
"""
def get_slice_md5(file_name):
    m = hashlib.md5()
    with open(file_name, 'rb') as fobj:
        data = fobj.read(256 * 1024)
        m.update(data)
    return m.hexdigest()

"""
获取内容MD5值
"""
def get_str_md5(content):
    m = hashlib.md5(content)  # 创建md5对象

"""
获取内容MD5值
"""
def traverse_files(folder_path):
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            file_path = os.path.join(root, file)
            file_md5 = calculate_md5_file(file_path)
            # print(file_path)  # 可以根据需求进行其他操作
            # print(file_md5)  # 可以根据需求进行其他操作

def calculate_md5_file(file_path):
    md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            md5.update(chunk)
    return md5.hexdigest()


"""
1、预创建
"""
def precreate(access_token, path, file_path):
    """
    precreate
    """
    #    Enter a context with an instance of the API client
    with openapi_client.ApiClient() as api_client:
        # Create an instance of the API class
        api_instance = fileupload_api.FileuploadApi(api_client)

        isdir = 0  # int | isdir
        size = os.path.getsize(file_path) #获取上传文件大小
        autoinit = 1  # int | autoinit

        kilobytes = 1024
        megabytes = kilobytes * 1024
        chunksize = int(32 * megabytes)  # default chunksize
        paths = []
        md5s = []
        if size > chunksize:
            # file_diretory = os.path.dirname(file_path) #获取目录路径
            file_diretory = os.getcwd() #获取目录路径
            tmp_path = os.path.join(file_diretory, 'tmp') #临时文件目录
            if not os.path.exists(tmp_path):
                os.makedirs(tmp_path)
            split(file_path, tmp_path, chunksize)
            paths, md5s = get_files_md5(tmp_path)
            # print(md5s)
            list_as_string = str(md5s)
            block_list = list_as_string.replace("'", '"')  # str | 由MD5字符串组成的list
            # print(block_list)
        else:
            tmp_path = None
            block_list = ''  # str | 由MD5字符串组成的list
            file_md5 = get_file_md5(file_path)
            block_list = block_list + '["{}"]' .format(file_md5)  #放入block_list
            # print(block_list)

        rtype = 3  # int | rtype (optional)

        # example passing only required values which don't have defaults set
        # and optional values
        try:
            api_response = api_instance.xpanfileprecreate(
                access_token, path, isdir, size, autoinit, block_list, rtype=rtype)
            # logging.info(api_response)
            if api_response['errno'] == -6:
                logging.error("疑似access_token过期: %s" % api_response['errmsg'])
            uploadid = api_response['uploadid'] #获取预上传返回的uploadid，传给upload和create函数
            # block_list_id = api_response['block_list']
        except openapi_client.ApiException as e:
            logging.error("Exception when calling FileuploadApi -> xpanfileprecreate: %s\n" % e)
        # print(access_token, path, isdir, size, uploadid, block_list, rtype, file_path, paths)
        return access_token, path, isdir, size, uploadid, block_list, rtype, file_path, paths, tmp_path

"""
2、上传
"""
def upload(uploadid, path, file_path, access_token, paths):
    """
    upload
    """
    # print(uploadid, path, file_path, access_token, paths)

    # Enter a context with an instance of the API client
    with openapi_client.ApiClient() as api_client:
        # Create an instance of the API class
        api_instance = fileupload_api.FileuploadApi(api_client)
        # access_token = "" # str |
        # path = "/apps/hhhkoo/a.txt"  # str |
        # uploadid = ""  # str |
        type = "tmpfile"  # str |

        if len(paths) == 0:
            partseq = '0'
            try:
                file = open(file_path, 'rb') # file_type | 要进行传送的本地文件分片
            except Exception as e:
                logging.error("Exception when open file: %s\n" % e)
                exit(-1)

            # example passing only required values which don't have defaults set
            # and optional values
            try:
                api_instance.pcssuperfile2(access_token, partseq, path, uploadid, type, file=file)
            except openapi_client.ApiException as e:
                logging.error("Exception when calling FileuploadApi -> pcssuperfile2: %s\n" % e)
        else:
            for index, value in enumerate(paths):
                partseq = str(index)
                logging.info(f"Uploading：{value}({index + 1}/{len(paths)})") # 进度打屏
                try:
                    file = open(value, 'rb') # file_type | 要进行传送的本地文件分片
                except Exception as e:
                    logging.error("Exception when open file: %s\n" % e)
                    exit(-1)

                # example passing only required values which don't have defaults set
                # and optional values
                try:
                    api_instance.pcssuperfile2(access_token, partseq, path, uploadid, type, file=file)
                except openapi_client.ApiException as e:
                    logging.error("Exception when calling FileuploadApi -> pcssuperfile2: %s\n" % e)

"""
3、创建文件
"""
def create(access_token, path, isdir, size, uploadid, block_list, rtype, tmp_path):
    """
    create
    """
    # Enter a context with an instance of the API client
    with openapi_client.ApiClient() as api_client:
        # Create an instance of the API class
        api_instance = fileupload_api.FileuploadApi(api_client)

        # example passing only required values which don't have defaults set
        # and optional values
        try:
            api_response = api_instance.xpanfilecreate(
                access_token, path, isdir, size, uploadid, block_list, rtype=rtype)
            if api_response["errno"] != 0:
                logging.error(api_response)
            else:
                logging.info(f"Uploaded: {api_response['path']} | Size:{api_response['size'] / 1048576} MB")
                if tmp_path != None:
                    if os.path.exists(tmp_path):
                        shutil.rmtree(tmp_path)
        except openapi_client.ApiException as e:
            logging.error("Exception when calling FileuploadApi -> xpanfilecreate: %s\n" % e)