#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import ssl
import urllib3
from datetime import datetime, timezone, timedelta
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator

# SSL警告を無効化（必要に応じて）
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 設定
BASE_URL = "https://www.dlri.co.jp"
TARGET_URL = "https://www.dlri.co.jp/members/nishihama.html"
OUTPUT_FILE = "feed.xml"
MAX_ITEMS = 50  # RSSに含める最大アイテム数

# 日本のタイムゾーン（JST: UTC+9）
JST = timezone(timedelta(hours=9))

def fetch_html(url):
    """HTMLを取得する（SSLエラー対応）"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    try:
        # 方法1: SSL検証を無効にする（自己署名証明書対応）
        response = requests.get(url, headers=headers, timeout=30, verify=False)
        response.raise_for_status()
        response.encoding = 'utf-8'
        return response.text
        
    except requests.exceptions.SSLError as e:
        print(f"SSLエラーが発生しました。代替方法で再試行します...")
        
        try:
            # 方法2: カスタムSSLコンテキストを使用
            session = requests.Session()
            session.verify = False
            
            # より寛容なSSL設定
            session.mount('https://', requests.adapters.HTTPAdapter(
                pool_connections=10,
                pool_maxsize=10,
                max_retries=3
            ))
            
            response = session.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            response.encoding = 'utf-8'
            return response.text
            
        except requests.exceptions.RequestException as e2:
            print(f"代替方法でもエラー: {e2}")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"HTML取得エラー: {e}")
        return None

def parse_reports(html):
    """HTMLからレポート情報を抽出する"""
    soup = BeautifulSoup(html, 'html.parser')
    reports = []

    # 執筆レポート一覧セクションを探す
    sections = soup.find_all('section')
    
    for section in sections:
        # タイトルが「執筆レポート一覧」のセクションを特定
        title_elem = section.find('h3', class_='title')
        if not title_elem:
            continue
        if '執筆レポート一覧' not in title_elem.get_text():
            continue
        
        # レポートリストを取得
        list_container = section.find('ul', class_='borderList')
        if not list_container:
            # 別のクラス名で検索
            list_container = section.find('ul', class_='moreList-js')
        if not list_container:
            continue
        
        # 各レポートを解析
        for item in list_container.find_all('li'):
            link = item.find('a')
            if not link:
                continue
            
            # タイトルとURLを取得
            title = link.get_text(strip=True)
            url = link.get('href', '')
            if url.startswith('/'):
                url = urljoin(BASE_URL, url)
            
            # 日付を抽出（例: "2026.09.02　..."）
            date_match = re.match(r'^(\d{4})\.(\d{2})\.(\d{2})\s*', title)
            if date_match:
                year, month, day = map(int, date_match.groups())
                pub_date = datetime(year, month, day, 0, 0, 0, tzinfo=JST)
                # タイトルから日付部分を除去
                title_clean = re.sub(r'^(\d{4}\.\d{2}\.\d{2}\s*)', '', title)
            else:
                # 日付がない場合は現在時刻を使用
                pub_date = datetime.now(JST)
                title_clean = title
            
            # 説明文を取得（あれば）
            description = ""
            # リンクの兄弟要素に説明がある場合
            next_sibling = link.find_next_sibling()
            if next_sibling and next_sibling.name:
                description = next_sibling.get_text(strip=True)
            
            reports.append({
                'title': title_clean,
                'url': url,
                'pub_date': pub_date,
                'description': description
            })
        
        break  # 最初の一致するセクションのみ処理
    
    return reports

def generate_rss(reports, output_file):
    """RSSフィードを生成する"""
    fg = FeedGenerator()
    fg.title("西濵徹 執筆レポート - 第一ライフ資産運用経済研究所")
    fg.link(href=TARGET_URL, rel="alternate")
    fg.description("第一ライフ資産運用経済研究所 西濵徹氏の執筆レポート一覧")
    fg.language("ja")
    
    # フィードの最終更新日時
    if reports:
        latest_date = max(r['pub_date'] for r in reports)
        fg.lastBuildDate(latest_date)
    
    # 各レポートをフィードに追加
    for report in reports[:MAX_ITEMS]:
        fe = fg.add_entry()
        fe.title(report['title'])
        fe.link(href=report['url'])
        fe.pubDate(report['pub_date'])
        if report['description']:
            fe.description(report['description'])
        else:
            # 説明がない場合はタイトルを再利用
            fe.description(f"{report['title']}")
    
    # RSSファイルに保存
    fg.rss_file(output_file, pretty=True)
    print(f"RSSフィードを生成しました: {output_file}")
    print(f"アイテム数: {len(reports[:MAX_ITEMS])}")

def test_connection(url):
    """接続テスト用の簡易関数"""
    try:
        response = requests.get(url, timeout=10, verify=False)
        print(f"接続テスト成功: ステータスコード {response.status_code}")
        return True
    except Exception as e:
        print(f"接続テスト失敗: {e}")
        return False

def main():
    """メイン処理"""
    print("=" * 50)
    print("西濵徹 RSSフィード生成ツール")
    print("=" * 50)
    
    # 接続テスト
    print(f"\n接続テスト: {TARGET_URL}")
    if not test_connection(TARGET_URL):
        print("接続に失敗しました。ネットワーク環境を確認してください。")
        return
    
    print("\nHTMLを取得中...")
    html = fetch_html(TARGET_URL)
    if not html:
        print("HTMLの取得に失敗しました")
        return
    
    print("HTML取得成功！（サイズ: {} バイト）".format(len(html)))
    
    print("\nレポート情報を抽出中...")
    reports = parse_reports(html)
    if not reports:
        print("レポートが見つかりませんでした")
        print("HTMLの構造が変更されている可能性があります。")
        return
    
    print(f"{len(reports)}件のレポートを取得しました")
    
    print("\nRSSフィードを生成中...")
    generate_rss(reports, OUTPUT_FILE)
    print("\n完了！")

if __name__ == "__main__":
    main()
