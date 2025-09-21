import requests
import json
from PIL import Image
from io import BytesIO
from math import ceil
import pandas as pd
import time
import os
import random

def getTimelineData(x, y, udt=None):
    """获取特定坐标的所有历史街景数据"""
    if udt is None:
        udt = time.strftime("%Y%m%d")
    
    # 获取当前街景ID
    url = f"https://mapsv0.bdimg.com/?qt=qsdata&x={x}&y={y}&udt={udt}"
    try:
        response = requests.get(url)
        data = json.loads(response.text)
        
        if 'content' not in data or not data['content']:
            print(f"坐标({x}, {y})无街景数据")
            return []
        
        content = data['content']
        current_id = content.get('id')
        if not current_id:
            print(f"无法获取当前ID")
            return []
        
        # 获取历史街景数据
        metadata_url = f"https://mapsv0.bdimg.com/?qt=sdata&sid={current_id}"
        meta_response = requests.get(metadata_url)
        meta_data = json.loads(meta_response.text)
        
        # 提取TimeLine数据
        timeline = []
        if 'content' in meta_data:
            meta_content = meta_data['content']
            if isinstance(meta_content, list) and meta_content:
                meta_content = meta_content[0]
            
            if isinstance(meta_content, dict):
                timeline = meta_content.get('TimeLine', [])
        
        # 添加当前ID到结果
        result = [{'Year': 'current', 'ID': current_id}]
        
        # 添加历史记录
        if timeline:
            result.extend(timeline)
            
        return result
        
    except Exception as e:
        print(f"获取时间线数据出错: {e}")
        import traceback
        traceback.print_exc()
        return []

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
        newImg.paste(img, (col * w, row * h))
    
    return newImg

def downloadAllHistorical(x, y, zoom, save_folder, point_index):
    """下载指定坐标的所有历史街景图片"""
    imgPerRow = {1: 1, 2: 2, 3: 4, 4: 8}
    
    # 获取所有历史街景数据
    timeline = getTimelineData(x, y)
    if not timeline:
        print(f"坐标({x}, {y})未找到街景数据")
        return 0
    
    print(f"发现{len(timeline)}个历史记录")
    success_count = 0
    
    for item in timeline:
        year = item.get('Year', 'UNKNOWN')
        
        # 跳过current年份的街景
        if year == 'current':
            continue
            
        img_id = item.get('ID')
        
        if not img_id:
            continue
            
        # 生成带年份的文件名
        fp = os.path.join(save_folder, f"{point_index:05d}_{year}.jpg")
        
        # 如果文件已存在则跳过
        if os.path.exists(fp):
            print(f"文件已存在，跳过: {fp}")
            success_count += 1
            continue
        
        try:
            print(f"使用ID: {img_id} 下载{year}年的街景")
            # 下载并合成图片
            imgBytes = getImageBytesList(img_id, z=zoom)
            if not imgBytes:
                continue
                
            imgList = bytesList2ImgList(imgBytes)
            if not imgList:
                continue
                
            img = mergeImage(imgList, imgPerRow[zoom])
            if not img:
                continue
                
            img.save(fp)
            print(f"成功保存图片: {fp}")
            success_count += 1
            
            # 随机延时，避免请求过于频繁
            time.sleep(random.randint(1, 3))
            
        except Exception as e:
            print(f"下载或保存图片时出错: {e}")
    
    return success_count

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
    try:
        # 确保坐标格式正确，去除可能的空格
        coords = coords.replace(" ", "")
        url = f"http://api.map.baidu.com/geoconv/v1/?coords={coords}&from=1&to=6&ak={ak}"
        
        # 增加请求头部和超时设置
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        response = requests.get(url, headers=headers, timeout=10)

        
        data = json.loads(response.text)
        
        if data.get('status') != 0:
            print(f"坐标转换失败: {data}")
            return []
            
        points = [[x["x"], x["y"]] for x in data['result']]
        return points
    except Exception as e:
        print(f"坐标转换错误: {e}")
        # 打印更详细的错误信息
        import traceback
        traceback.print_exc()
        return []

def baiduAllHistoricalImgDownloader(pointsCsvPath, toFolderPath, ak, zoom=3):
    """
    批量下载所有百度历史街景图片
    pointsCsvPath: WGS84坐标点CSV文件路径
    toFolderPath: 图片保存文件夹路径
    ak: 百度地图API密钥
    zoom: 缩放级别
    """
    # 创建保存目录
    try:
        os.makedirs(toFolderPath, exist_ok=True)
        save_folder = os.path.join(toFolderPath, "all_historical_views")
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
        total_success = 0
        
        for i, (x, y) in enumerate(points):
            print(f"处理点 {i+1}/{len(points)}: 坐标({x}, {y})")
            success_count = downloadAllHistorical(x, y, zoom, save_folder, i)
            total_success += success_count
            
            # 随机延时，避免请求过于频繁
            time.sleep(random.randint(2, 5))
        
        print(f"下载完成! 共处理{len(points)}个点，成功下载{total_success}张历史图片。")
    except Exception as e:
        print(f"下载过程中发生错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # 使用示例 - 确保使用正确的AK
    baiduAllHistoricalImgDownloader("resources/example.csv", "街景图片", "baidu-map-ak", zoom=3)