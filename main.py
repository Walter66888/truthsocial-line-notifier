import os
import json
import time
import logging
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from datetime import datetime

# 設定日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 載入環境變數
load_dotenv()

# 常量設定
TRUTH_SOCIAL_URL = "https://truthsocial.com/@realDonaldTrump"
LINE_API_URL = "https://api.line.me/v2/bot/message/push"
LINE_CHANNEL_TOKEN = os.getenv("LINE_CHANNEL_TOKEN")
LINE_USER_ID = os.getenv("LINE_USER_ID")
LAST_POST_FILE = "last_post_id.txt"

def get_last_processed_id():
    """讀取最後處理的貼文ID"""
    try:
        with open(LAST_POST_FILE, "r") as f:
            return f.read().strip()
    except FileNotFoundError:
        logger.info("找不到上次的貼文記錄，將創建新檔案")
        return ""

def save_last_processed_id(post_id):
    """保存最後處理的貼文ID"""
    with open(LAST_POST_FILE, "w") as f:
        f.write(post_id)

def get_trump_posts():
    """爬取Truth Social上Trump的最新貼文"""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        
        response = requests.get(TRUTH_SOCIAL_URL, headers=headers)
        if response.status_code != 200:
            logger.error(f"獲取網頁失敗: {response.status_code}")
            return []
            
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 查找包含貼文的元素 (這部分可能需要根據實際頁面結構調整)
        posts = soup.select('div.status-card, article.status')
        
        results = []
        for post in posts:
            try:
                # 獲取貼文ID (格式可能因平台而異)
                post_id_elem = post.select_one('[data-id]')
                if post_id_elem:
                    post_id = post_id_elem.get('data-id')
                else:
                    post_id = post.get('id', f"unknown-{int(time.time())}")
                
                # 獲取貼文內容
                content_elem = post.select_one('.status__content, .post-content')
                content = content_elem.get_text().strip() if content_elem else "內容無法解析"
                
                # 獲取貼文時間
                timestamp_elem = post.select_one('time, .status__relative-time')
                post_time = timestamp_elem.get('datetime') if timestamp_elem else datetime.now().isoformat()
                
                # 獲取原始貼文連結
                link_elem = post.select_one('a.status__relative-time, a.post-link')
                link = link_elem.get('href') if link_elem else TRUTH_SOCIAL_URL
                if not link.startswith('http'):
                    link = f"https://truthsocial.com{link}"
                
                results.append({
                    'id': post_id,
                    'content': content,
                    'timestamp': post_time,
                    'link': link
                })
            except Exception as e:
                logger.error(f"解析貼文時出錯: {e}")
        
        return results
    except Exception as e:
        logger.error(f"爬取過程出錯: {e}")
        return []

def send_line_notification(message):
    """發送LINE通知"""
    if not LINE_CHANNEL_TOKEN or not LINE_USER_ID:
        logger.error("LINE配置不完整，無法發送通知")
        return False
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_CHANNEL_TOKEN}"
    }
    
    payload = {
        "to": LINE_USER_ID,
        "messages": [
            {
                "type": "text",
                "text": message
            }
        ]
    }
    
    try:
        response = requests.post(LINE_API_URL, headers=headers, data=json.dumps(payload))
        if response.status_code == 200:
            logger.info("LINE通知發送成功")
            return True
        else:
            logger.error(f"LINE通知發送失敗: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logger.error(f"發送LINE通知時出錯: {e}")
        return False

def main():
    """主函數"""
    logger.info("開始檢查Truth Social最新貼文")
    
    # 獲取上次處理的貼文ID
    last_post_id = get_last_processed_id()
    logger.info(f"上次處理的貼文ID: {last_post_id or '無'}")
    
    # 爬取最新貼文
    posts = get_trump_posts()
    if not posts:
        logger.info("沒有找到貼文或爬取失敗")
        return
        
    logger.info(f"找到 {len(posts)} 個貼文")
    
    # 排序貼文，確保按時間順序處理
    posts.sort(key=lambda x: x.get('timestamp', ''))
    
    # 檢查新貼文
    new_posts = []
    newest_post_id = last_post_id
    
    for post in posts:
        post_id = post.get('id')
        
        # 如果沒有上次的記錄，或者這是個新貼文
        if not last_post_id or post_id > last_post_id:
            new_posts.append(post)
            if not newest_post_id or post_id > newest_post_id:
                newest_post_id = post_id
    
    # 如果有新貼文，發送通知
    if new_posts:
        logger.info(f"發現 {len(new_posts)} 個新貼文")
        
        for post in new_posts:
            message = f"Donald Trump 有新貼文！\n\n{post.get('content')}\n\n連結: {post.get('link')}"
            if send_line_notification(message):
                logger.info(f"成功發送貼文 ID {post.get('id')} 的通知")
        
        # 更新最後處理的貼文ID
        save_last_processed_id(newest_post_id)
        logger.info(f"更新最後處理的貼文ID為: {newest_post_id}")
    else:
        logger.info("沒有發現新貼文")

if __name__ == "__main__":
    main()
