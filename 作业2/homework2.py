import os
import re
import time
import json
from typing import List, Dict
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


BASE_URL = "https://www.sucai999.com/pic/cate/265_324-{}.html"
SAVE_DIR = "downloaded_images"
MAX_PAGES = 10 


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.sucai999.com/",
}


def fetch_page(url: str) -> BeautifulSoup:
    """请求页面并返回 BeautifulSoup 对象"""
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        if not response.encoding or response.encoding.lower() == "iso-8859-1":
            response.encoding = response.apparent_encoding
        return BeautifulSoup(response.text, "html.parser")
    except Exception as e:
        print(f"[ERROR] Failed to fetch {url}: {e}")
        return None


def extract_image_urls(page_soup: BeautifulSoup, base_url: str) -> List[Dict[str, str]]:
    """从页面中提取图片信息（URL、标题等）"""
    image_data_list = []
    
    # 常见的图片容器选择器
    # 需要根据实际网页结构调整
    image_containers = page_soup.find_all("img")
    
    for img_tag in image_containers:
        # 尝试多种属性获取图片URL
        img_url = None
        
        # 优先尝试 data-original（懒加载）
        if img_tag.get("data-original"):
            img_url = img_tag["data-original"]
        # 其次尝试 data-src
        elif img_tag.get("data-src"):
            img_url = img_tag["data-src"]
        # 最后尝试 src
        elif img_tag.get("src"):
            img_url = img_tag["src"]
        
        if not img_url:
            continue
        
        # 跳过小图标、logo等
        if any(skip in img_url.lower() for skip in ["logo", "icon", "avatar", "banner"]):
            continue
        
        # 转换为绝对URL
        if img_url.startswith("//"):
            img_url = "https:" + img_url
        elif img_url.startswith("/"):
            img_url = urljoin(base_url, img_url)
        elif not img_url.startswith("http"):
            img_url = urljoin(base_url, img_url)
        
        # 提取标题（从alt或title属性，或从父元素）
        title = (
            img_tag.get("alt", "") or
            img_tag.get("title", "") or
            ""
        ).strip()
        
        # 如果标题为空，尝试从父元素获取
        if not title:
            parent = img_tag.find_parent("a") or img_tag.find_parent("div")
            if parent:
                title_text = parent.get_text(strip=True)
                if title_text and len(title_text) < 100:
                    title = title_text
        
        # 如果没有标题，使用文件名
        if not title:
            parsed_url = urlparse(img_url)
            title = os.path.basename(parsed_url.path) or f"image_{len(image_data_list)}"
        
        image_data_list.append({
            "url": img_url,
            "title": title,
            "filename": os.path.basename(urlparse(img_url).path) or f"image_{len(image_data_list)}.jpg"
        })
    
    return image_data_list


def download_image(img_url: str, save_path: str) -> bool:
    """下载单张图片"""
    try:
        response = requests.get(img_url, headers=HEADERS, timeout=30, stream=True)
        response.raise_for_status()
        
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        
        with open(save_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        
        return True
    except Exception as e:
        print(f"[ERROR] Failed to download {img_url}: {e}")
        return False


def sanitize_filename(filename: str) -> str:
    """清理文件名，移除非法字符"""
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    filename = filename.strip('. ')
    if not filename:
        filename = "unnamed"
    return filename[:200]  # 限制文件名长度


def crawl_images(max_pages: int = MAX_PAGES) -> List[Dict[str, str]]:
    """爬取指定页数的图片数据"""
    all_image_data = []
    seen_urls = set()
    
    print(f"开始爬取菜鸟图库图片，共 {max_pages} 页...")
    
    for page_num in range(1, max_pages + 1):
        page_url = BASE_URL.format(page_num)
        print(f"\n[第 {page_num}/{max_pages} 页] 正在访问: {page_url}")
        
        page_soup = fetch_page(page_url)
        if not page_soup:
            print(f"  跳过第 {page_num} 页")
            continue
        
        image_data_list = extract_image_urls(page_soup, page_url)
        print(f"  找到 {len(image_data_list)} 张图片")
        
        for img_data in image_data_list:
            img_url = img_data["url"]
            
            # 去重
            if img_url in seen_urls:
                continue
            seen_urls.add(img_url)
            
            all_image_data.append(img_data)
            print(f"    - {img_data['title'][:50]}...")
        
        # 避免请求过快
        time.sleep(1)
    
    print(f"\n总共收集到 {len(all_image_data)} 张图片")
    return all_image_data


def save_images(image_data_list: List[Dict[str, str]], download: bool = True):
    """保存图片数据，可选择是否下载图片"""
    os.makedirs(SAVE_DIR, exist_ok=True)
    
    # 保存图片信息到JSON
    json_path = os.path.join(SAVE_DIR, "image_data.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(image_data_list, f, ensure_ascii=False, indent=2)
    print(f"\n图片信息已保存到: {json_path}")
    
    if not download:
        return
    
    # 下载图片
    print(f"\n开始下载图片到 {SAVE_DIR} 目录...")
    success_count = 0
    
    for idx, img_data in enumerate(image_data_list, start=1):
        img_url = img_data["url"]
        title = img_data["title"]
        filename = sanitize_filename(img_data["filename"])
        
        # 确保文件扩展名
        if not filename.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')):
            filename += ".jpg"
        
        save_path = os.path.join(SAVE_DIR, f"{idx:04d}_{filename}")
        
        print(f"[{idx}/{len(image_data_list)}] 下载: {title[:50]}...")
        
        if download_image(img_url, save_path):
            success_count += 1
        
        # 避免请求过快
        time.sleep(0.5)
    
    print(f"\n下载完成！成功下载 {success_count}/{len(image_data_list)} 张图片")


def main():
    """主函数"""
    print("=" * 60)
    print("菜鸟图库图片爬虫")
    print("=" * 60)
    
    # 爬取图片数据
    image_data_list = crawl_images(max_pages=MAX_PAGES)
    
    if not image_data_list:
        print("\n未找到任何图片数据")
        return
    
    # 保存数据并下载图片
    save_images(image_data_list, download=True)
    
    print("\n" + "=" * 60)
    print("爬取完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()

