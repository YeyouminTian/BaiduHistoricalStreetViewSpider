# 百度历史街景图片爬取
# 爬取百度街景图片，支持指定年份和坐标点
import requests
import json
from PIL import Image
from io import BytesIO
from math import ceil
import pandas as pd
import time
import os
import random

def getImageID(x, y, year=None, udt=None):
    """
    获取特定坐标的全景图ID，支持历史年份查询
    x, y: BD09MC坐标
    year: 可选，指定要下载的年份，如"2013"
    udt: 可选，日期参数
    """
    if udt is None:
        udt = time.strftime("%Y%m%d")
    
    # 第一步：获取当前街景ID
    url = f"https://mapsv0.bdimg.com/?qt=qsdata&x={x}&y={y}&udt={udt}"
    try:
        response = requests.get(url)
        data = json.loads(response.text)
        
        if 'content' not in data or not data['content']:
            print(f"坐标({x}, {y})无街景数据")
            return None
        
        content = data['content']
        
        # 获取当前ID (注意：API返回的是小写的'id')
        current_id = content.get('id')
        if not current_id:
            print(f"无法获取当前ID")
            return None
        
        print(f"当前ID: {current_id}")
        
        # 如果没有指定年份，直接返回当前ID
        if year is None:
            return current_id
        
        # 第二步：使用ID获取历史街景数据
        metadata_url = f"https://mapsv0.bdimg.com/?qt=sdata&sid={current_id}"
        meta_response = requests.get(metadata_url)
        meta_data = json.loads(meta_response.text)
        
        # 提取TimeLine数据
        timeline = None
        if 'content' in meta_data:
            meta_content = meta_data['content']
            if isinstance(meta_content, list) and meta_content:
                meta_content = meta_content[0]
            
            if isinstance(meta_content, dict):
                timeline = meta_content.get('TimeLine')
        
        if not timeline:
            print("未找到历史街景数据")
            return current_id
        
        print(f"发现{len(timeline)}个历史记录")
        
        # 打印所有TimeLine项
        for i, item in enumerate(timeline):
            year_val = item.get('Year', 'UNKNOWN')
            timeline_val = item.get('TimeLine', 'UNKNOWN')
            id_val = item.get('ID', 'UNKNOWN')
            print(f"历史记录[{i}]: Year={year_val}, TimeLine={timeline_val}, ID={id_val}")
        
        # 查找指定年份的历史街景
        year_str = str(year)
        for item in timeline:
            if item.get('Year') == year_str:
                match_id = item.get('ID')
                print(f"成功匹配{year}年的街景ID: {match_id}")
                return match_id
        
        # 如果没找到指定年份，返回当前ID
        print(f"未找到{year}年的街景记录，使用当前街景")
        return current_id
        
    except Exception as e:
        print(f"获取图像ID时出错: {e}")
        import traceback
        traceback.print_exc()
        return None

def getImageBytesList(sid, z=2):
    """获取街景图片数据"""
    if z == 2:
        xrange, yrange = 1, 2
    elif z == 3:
        xrange, yrange = 2, 4
    elif z == 1:
        xrange, yrange = 1, 1
    elif z == 4:
        xrange, yrange = 4, 8
    
    imgBytes = []
    for x in range(xrange):
        for y in range(yrange):
            url = f"https://mapsv1.bdimg.com/?qt=pdata&sid={sid}&pos={x}_{y}&z={z}&from=PC"
            try:
                response = requests.get(url)
                if response.status_code == 200:
                    imgBytes.append(response.content)
                else:
                    print(f"下载图片失败: HTTP {response.status_code}")
                    return []
            except Exception as e:
                print(f"请求图片出错: {e}")
                return []
    return imgBytes

def bytes2Img(imgByte):
    """字节流转图像"""
    try:
        return Image.open(BytesIO(imgByte))
    except Exception as e:
        print(f"图像解析失败: {e}")
        return None

def bytesList2ImgList(x):
    """字节流列表转图像列表"""
    imgList = []
    for imgByte in x:
        img = bytes2Img(imgByte)
        if img:
            imgList.append(img)
    return imgList

def mergeImage(imgList, imgNumPerRow):
    """合并多张图片"""
    if not imgList:
        print("没有有效图片可合并")
        return None
    
    w, h = imgList[0].size
    rowNum = ceil(len(imgList) / imgNumPerRow)
    width = w * imgNumPerRow
    height = h * rowNum
    newImg = Image.new("RGB", (width, height))
    
    for i, img in enumerate(imgList):
        row = i // imgNumPerRow
        col = i % imgNumPerRow
        newImg.paste(img, (col * w, row * h))  # 修正坐标计算
    
    return newImg

def download(x, y, zoom, fp, year=None, udt=None):
    """
    下载指定坐标和年份的街景图片
    x, y: BD09MC坐标
    zoom: 缩放级别
    fp: 保存路径
    year: 可选，指定要下载的年份，如"2013"
    udt: 可选，日期参数
    """
    imgPerRow = {1: 1, 2: 2, 3: 4, 4: 8}
    
    # 获取图像ID，可指定年份
    imgId = getImageID(x, y, year, udt)
    if not imgId:
        print(f"坐标({x}, {y})未找到街景数据")
        return False
    
    try:
        print(f"使用ID: {imgId} 下载街景")
        # 下载并合成图片
        imgBytes = getImageBytesList(imgId, z=zoom)
        if not imgBytes:
            return False
            
        imgList = bytesList2ImgList(imgBytes)
        if not imgList:
            return False
            
        img = mergeImage(imgList, imgPerRow[zoom])
        if not img:
            return False
            
        img.save(fp)
        return True
    except Exception as e:
        print(f"下载或保存图片时出错: {e}")
        return False

def inputPoints(fp):
    """读取WGS84坐标点文件"""
    try:
        points = pd.read_csv(fp, encoding="utf8")
        points = points.to_numpy().tolist()
        points100 = []
        for i, (x, y) in enumerate(points):
            n = i // 100
            if len(points100) == n:
                points100 += [f"{x},{y}"]
            else:
                points100[n] += f";{x},{y}"
        return points100
    except Exception as e:
        print(f"读取坐标点文件出错: {e}")
        return []

def convertWGStoBD09MC(coords, ak):
    """将WGS84坐标转换为BD09MC坐标"""
    url = f"http://api.map.baidu.com/geoconv/v1/?coords={coords}&from=1&to=6&ak={ak}"
    try:
        response = requests.get(url)
        data = json.loads(response.text)
        
        if data.get('status') != 0:
            print(f"坐标转换失败: {data}")
            return []
            
        points = [[x["x"], x["y"]] for x in data['result']]
        return points
    except Exception as e:
        print(f"坐标转换错误: {e}")
        return []

def baiduHistoricalImgDownloader(pointsCsvPath, toFolderPath, ak, zoom=3, year=None, udt=None):
    """
    批量下载指定年份的百度街景图片
    pointsCsvPath: WGS84坐标点CSV文件路径
    toFolderPath: 图片保存文件夹路径
    ak: 百度地图API密钥
    zoom: 缩放级别
    year: 可选，指定要下载的年份，如"2013"
    udt: 可选，日期参数
    """
    # 创建保存目录
    try:
        os.makedirs(toFolderPath, exist_ok=True)
        
        # 年份信息添加到文件夹名称
        year_str = f"_{year}" if year else ""
        save_folder = os.path.join(toFolderPath, f"street_view{year_str}")
        os.makedirs(save_folder, exist_ok=True)
        
        # 读取并转换坐标点
        points100 = inputPoints(pointsCsvPath)
        if not points100:
            print("未获取到有效坐标点")
            return
            
        points = []
        for p in points100:
            converted = convertWGStoBD09MC(p, ak)
            if converted:
                points.extend(converted)
                # 添加延时，避免请求过于频繁
                time.sleep(random.randint(1, 2))
        
        if not points:
            print("坐标转换失败，未获取有效BD09MC坐标")
            return
            
        print(f"共有{len(points)}个坐标点需要处理")
        success_count = 0
        
        for i, (x, y) in enumerate(points):
            fp = os.path.join(save_folder, f"{i:0>5d}.jpg")
            
            # 如果文件已存在则跳过
            if os.path.exists(fp):
                print(f"文件已存在，跳过: {fp}")
                success_count += 1
                continue
            
            print(f"处理点 {i+1}/{len(points)}: 坐标({x}, {y})")
            if download(x, y, zoom, fp, year, udt):
                success_count += 1
                print(f"成功保存图片: {fp}")
            
            # 随机延时，避免请求过于频繁
            time.sleep(random.randint(2, 5))
        
        print(f"下载完成! 共{len(points)}个点，成功下载{success_count}个图片。")
    except Exception as e:
        print(f"下载过程中发生错误: {e}")

if __name__ == "__main__":
    # 使用示例
    baiduHistoricalImgDownloader("resources/example.csv", "街景图片", "baidu-map-ak", zoom=3, year="2019")
    # 如果不指定年份，则下载最新的街景
    # baiduHistoricalImgDownloader("100m间隔点坐标xy.csv", "街景图片", "您的百度地图AK", zoom=3)
    pass