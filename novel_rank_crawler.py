# -*- coding: utf-8 -*-

from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
import pandas as pd
import time
import random

# -------------------------- 配置项（需根据目标网站修改） --------------------------
TARGET_URL = "https://chuangshi.qq.com/rank/526080_1"  
SCROLL_TIMES = 10  # 滚动加载次数（根据榜单长度调整）
DELAY_RANGE = (1, 5)  # 随机延迟范围（秒），模拟人类行为
# 标签匹配规则（需用浏览器F12检查目标网站后修改）
TAG_CONFIG = {
    "item_tag": "div",
    "item_class": "book-simple",
    "title_tag": "a", 
    "intro_tag": "div",
    "intro_class": "book-intro",  # 简介对应的标签+class
    "author_tag": "span",
    "author_class": "author",
    "heat_tag": "span",
    "heat_class": "rect"
}
   
OUTPUT_FILE = "创世中文网月票榜单数据.csv"  # 输出文件路径

# -------------------------- 核心函数 --------------------------
def get_random_ua() -> str:
    """生成随机User-Agent，规避UA检测"""
    try:
        ua = UserAgent()
        return ua.random
    except:
        # 备用UA（防止fake_useragent失效）
        return "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

def crawl_novel_rank() -> None:
    """主爬取函数（新增自动翻页逻辑）"""
    # 初始化总数据列表（用于存储所有页面的数据）
    total_data_list = []

    # 1. 启动浏览器（隐藏自动化特征）
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,  # 调试时设为False（显示浏览器），正式爬取设为True
            args=[
                "--disable-blink-features=AutomationControlled",  # 禁用自动化检测
                "--user-agent=" + get_random_ua()
            ]
        )
        page = browser.new_page()

        # 2. 访问目标页面（随机延迟，模拟用户犹豫）
        time.sleep(random.uniform(*DELAY_RANGE))
        page.goto(TARGET_URL, wait_until="networkidle")  # 等待网络空闲后加载完成
        time.sleep(random.uniform(*DELAY_RANGE))

        # -------------------------- 新增：自动翻页循环 --------------------------
        page_num = 1  # 记录当前页码
        while True:
            print(f"\n===== 开始爬取第 {page_num} 页 =====")

            # 3. 模拟滚动加载当前页更多数据（原滚动逻辑保留）
            last_height = page.evaluate("document.body.scrollHeight")
            scroll_count = 0
            while scroll_count < SCROLL_TIMES:
                # 随机滚动到80%-95%高度（非直接到底）
                scroll_to = last_height * random.uniform(0.8, 0.95)
                page.evaluate(f"window.scrollTo(0, {scroll_to})")
                time.sleep(random.uniform(*DELAY_RANGE))
                
                # 检查是否加载新内容
                new_height = page.evaluate("document.body.scrollHeight")
                if new_height == last_height:
                    print("无新数据加载，停止滚动")
                    break
                last_height = new_height
                scroll_count += 1
                print(f"已滚动{scroll_count}次，加载更多数据...")

            # 4. 解析当前页内容
            page_content = page.content()
            soup = BeautifulSoup(page_content, "html.parser")

            # 5. 提取当前页数据（异常处理）
            novel_items = soup.find_all(TAG_CONFIG["item_tag"], class_=TAG_CONFIG["item_class"])
            if not novel_items:
                print("⚠️ 第 {page_num} 页未找到榜单数据")
                return
            
            current_page_data = []
            for idx, item in enumerate(novel_items):
                try:
                    title = item.find(TAG_CONFIG["title_tag"]).get_text(strip=True)
                    intro = item.find(TAG_CONFIG["intro_tag"], class_=TAG_CONFIG["intro_class"]).get_text(strip=True)
                    author = item.find(TAG_CONFIG["author_tag"], class_=TAG_CONFIG["author_class"]).get_text(strip=True)
                    heat = item.find(TAG_CONFIG["heat_tag"], class_=TAG_CONFIG["heat_class"]).get_text(strip=True)

                    current_page_data.append({
                        "小说名": title,
                        "简介": intro,
                        "作者": author,
                        "分类": heat
                    })
                    print(f"✅ 第 {page_num} 页 提取成功 [{idx+1}]: 《{title}》")
                except Exception as e:
                    print(f"❌ 第 {page_num} 页 提取失败 [{idx+1}]: {str(e)}")
            
            # 将当前页数据加入总列表
            total_data_list.extend(current_page_data)

            # -------------------------- 判断并点击下一页 --------------------------
            # 定位下一页按钮（根据你的页面代码，选择器是a.pagination-next）
            next_page_btn = page.query_selector("a.pagination-next")
            if not next_page_btn or page_num >= 10:
                if page_num >= 10:
                   print(f"\n===== 已爬取 {page_num} 页，达到目标页数，停止爬取 =====") 
                else:
                   print(f"\n===== 所有页面爬取完成，共爬取 {page_num} 页 =====")
                break  # 终止循环
            
            # 点击下一页并等待加载
            next_page_btn.click()
            page.wait_for_load_state("networkidle")  # 等待页面加载完成
            time.sleep(random.uniform(*DELAY_RANGE))
            page_num += 1

        # 关闭浏览器（移到翻页循环外，所有页爬完再关）
        browser.close()

    # 6. 保存所有页面的总数据（UTF-8编码避免中文乱码）
    if total_data_list:
        df = pd.DataFrame(total_data_list)
        df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")
        print(f"\n📊 爬取完成！共提取 {len(total_data_list)} 条有效数据，已保存至：{OUTPUT_FILE}")
    else:
        print("\n⚠️ 未提取到有效数据，无需保存")   

# -------------------------- 执行入口 --------------------------
if __name__ == "__main__":
    print("🚀 开始爬取小说榜单...")
    crawl_novel_rank()