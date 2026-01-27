#!/usr/bin/env python3
"""
금융IT 뉴스 자동 수집기
- RSS 피드에서 경제/IT 뉴스 수집
- 금융IT 관련 키워드로 필터링
- 마크다운 파일로 정리
"""

import feedparser
import re
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
import hashlib


@dataclass
class Article:
    title: str
    link: str
    summary: str
    source: str
    published: Optional[str] = None
    
    @property
    def id(self) -> str:
        return hashlib.md5(self.link.encode()).hexdigest()[:8]


class FinTechNewsCollector:
    """금융IT 뉴스 수집기"""
    
    # RSS 피드 소스
    RSS_FEEDS = {
        "한국경제": "https://www.hankyung.com/feed/finance",
        "매일경제": "https://www.mk.co.kr/rss/30100041/",
        "연합뉴스_경제": "https://www.yonhapnewstv.co.kr/category/news/economy/feed/",
        "지디넷코리아": "https://www.zdnet.co.kr/rss/news.xml",
        "IT조선": "http://it.chosun.com/rss/rss.xml",
        "전자신문": "https://rss.etnews.com/Section901.xml",
    }
    
    # 금융IT 관련 키워드 (카테고리별)
    KEYWORDS = {
        "금융_인프라": [
            "코어뱅킹", "차세대", "금융 클라우드", "클라우드 전환", "레거시",
            "금융 시스템", "전산 시스템", "DR센터", "재해복구", "금융 플랫폼"
        ],
        "디지털_금융": [
            "오픈뱅킹", "마이데이터", "핀테크", "디지털 전환", "DX",
            "간편결제", "모바일뱅킹", "인터넷뱅킹", "네오뱅크", "챌린저뱅크",
            "CBDC", "디지털화폐", "토큰증권", "STO"
        ],
        "금융_기술": [
            "금융 API", "오픈API", "금융 AI", "로보어드바이저", "챗봇",
            "블록체인", "분산원장", "RPA", "자동화", "금융 데이터"
        ],
        "보안_규제": [
            "금융보안", "전자금융", "금융위", "금감원", "FDS", "이상거래",
            "개인정보", "정보보호", "망분리", "제로트러스트", "금융규제"
        ],
        "금융권_동향": [
            "은행 IT", "금융권 개발", "금융 채용", "농협은행", "KB국민",
            "신한은행", "우리은행", "하나은행", "카카오뱅크", "토스뱅크",
            "금융공동망", "금융결제원", "코스콤"
        ],
        "ESG_금융": [
            "녹색금융", "ESG", "탄소금융", "지속가능금융", "그린본드",
            "사회적금융", "임팩트투자"
        ]
    }
    
    def __init__(self):
        self.articles: list[Article] = []
        self.filtered_articles: dict[str, list[Article]] = {}
    
    def fetch_all_feeds(self) -> None:
        """모든 RSS 피드에서 뉴스 수집"""
        print("📰 뉴스 수집 시작...")
        
        for source_name, feed_url in self.RSS_FEEDS.items():
            try:
                feed = feedparser.parse(feed_url)
                count = 0
                
                for entry in feed.entries[:30]:  # 각 소스에서 최대 30개
                    article = Article(
                        title=self._clean_text(entry.get("title", "")),
                        link=entry.get("link", ""),
                        summary=self._clean_text(entry.get("summary", entry.get("description", "")))[:300],
                        source=source_name,
                        published=entry.get("published", entry.get("updated", ""))
                    )
                    
                    if article.title and article.link:
                        self.articles.append(article)
                        count += 1
                
                print(f"  ✓ {source_name}: {count}개 수집")
                
            except Exception as e:
                print(f"  ✗ {source_name}: 수집 실패 - {e}")
        
        print(f"📊 총 {len(self.articles)}개 기사 수집 완료\n")
    
    def filter_by_keywords(self) -> None:
        """금융IT 키워드로 기사 필터링"""
        print("🔍 금융IT 키워드 필터링 중...")
        
        seen_links = set()
        
        for category, keywords in self.KEYWORDS.items():
            self.filtered_articles[category] = []
            
            for article in self.articles:
                # 중복 제거
                if article.link in seen_links:
                    continue
                
                # 제목 + 요약에서 키워드 검색
                text = f"{article.title} {article.summary}".lower()
                
                for keyword in keywords:
                    if keyword.lower() in text:
                        self.filtered_articles[category].append(article)
                        seen_links.add(article.link)
                        break
        
        total = sum(len(articles) for articles in self.filtered_articles.values())
        print(f"📊 금융IT 관련 기사 {total}개 필터링 완료\n")
        
        for category, articles in self.filtered_articles.items():
            if articles:
                print(f"  • {category}: {len(articles)}개")
    
    def generate_markdown(self, output_dir: str = "news") -> str:
        """마크다운 파일 생성"""
        today = datetime.now()
        filename = f"{today.strftime('%Y-%m-%d')}.md"
        filepath = Path(output_dir) / filename
        
        # 디렉토리 생성
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        # 마크다운 내용 생성
        content = self._build_markdown_content(today)
        
        # 파일 저장
        filepath.write_text(content, encoding="utf-8")
        print(f"\n✅ 마크다운 파일 생성: {filepath}")
        
        return str(filepath)
    
    def _build_markdown_content(self, date: datetime) -> str:
        """마크다운 컨텐츠 빌드"""
        lines = [
            f"# 🏦 금융IT 뉴스 | {date.strftime('%Y년 %m월 %d일')}",
            "",
            f"> 자동 수집 시간: {date.strftime('%Y-%m-%d %H:%M')} KST",
            "",
            "---",
            "",
        ]
        
        # 요약 통계
        total = sum(len(articles) for articles in self.filtered_articles.values())
        lines.extend([
            "## 📊 오늘의 요약",
            "",
            f"- 총 수집 기사: {len(self.articles)}개",
            f"- 금융IT 관련: {total}개",
            "",
        ])
        
        # 카테고리별 기사
        category_icons = {
            "금융_인프라": "🏗️",
            "디지털_금융": "📱",
            "금융_기술": "⚙️",
            "보안_규제": "🔒",
            "금융권_동향": "🏛️",
            "ESG_금융": "🌱",
        }
        
        for category, articles in self.filtered_articles.items():
            if not articles:
                continue
            
            icon = category_icons.get(category, "📰")
            display_name = category.replace("_", " ")
            
            lines.extend([
                f"## {icon} {display_name}",
                "",
            ])
            
            for article in articles[:10]:  # 카테고리당 최대 10개
                lines.extend([
                    f"### [{article.title}]({article.link})",
                    "",
                    f"**출처**: {article.source}",
                    "",
                    f"{article.summary}...",
                    "",
                    "---",
                    "",
                ])
        
        # 기사가 없는 경우
        if total == 0:
            lines.extend([
                "## 📭 오늘의 금융IT 뉴스",
                "",
                "오늘은 수집된 금융IT 관련 뉴스가 없습니다.",
                "",
            ])
        
        # 푸터
        lines.extend([
            "",
            "---",
            "",
            "*이 문서는 [fintech-news-tracker](https://github.com/username/fintech-news-tracker)에 의해 자동 생성되었습니다.*",
        ])
        
        return "\n".join(lines)
    
    def update_readme(self, output_dir: str = ".") -> None:
        """README.md의 최근 뉴스 섹션 업데이트"""
        readme_path = Path(output_dir) / "README.md"
        
        if not readme_path.exists():
            return
        
        today = datetime.now().strftime("%Y-%m-%d")
        total = sum(len(articles) for articles in self.filtered_articles.values())
        
        # 최근 5개 기사 추출
        recent_articles = []
        for articles in self.filtered_articles.values():
            recent_articles.extend(articles[:2])
        recent_articles = recent_articles[:5]
        
        # 업데이트 섹션 생성
        update_section = [
            "<!-- NEWS_START -->",
            f"### 📅 최근 업데이트: {today}",
            "",
            f"오늘 수집된 금융IT 뉴스: **{total}건**",
            "",
        ]
        
        if recent_articles:
            update_section.append("#### 주요 뉴스")
            update_section.append("")
            for article in recent_articles:
                update_section.append(f"- [{article.title}]({article.link})")
            update_section.append("")
        
        update_section.append(f"👉 [전체 뉴스 보기](./news/{today}.md)")
        update_section.append("<!-- NEWS_END -->")
        
        # README 업데이트
        content = readme_path.read_text(encoding="utf-8")
        
        pattern = r"<!-- NEWS_START -->.*?<!-- NEWS_END -->"
        new_section = "\n".join(update_section)
        
        if re.search(pattern, content, re.DOTALL):
            content = re.sub(pattern, new_section, content, flags=re.DOTALL)
        else:
            content += "\n\n" + new_section
        
        readme_path.write_text(content, encoding="utf-8")
        print("✅ README.md 업데이트 완료")
    
    @staticmethod
    def _clean_text(text: str) -> str:
        """HTML 태그 및 특수문자 정리"""
        # HTML 태그 제거
        text = re.sub(r"<[^>]+>", "", text)
        # 연속 공백 정리
        text = re.sub(r"\s+", " ", text)
        # 앞뒤 공백 제거
        return text.strip()


def main():
    print("=" * 50)
    print("🏦 금융IT 뉴스 자동 수집기")
    print("=" * 50)
    print()
    
    collector = FinTechNewsCollector()
    
    # 1. 뉴스 수집
    collector.fetch_all_feeds()
    
    # 2. 키워드 필터링
    collector.filter_by_keywords()
    
    # 3. 마크다운 생성
    collector.generate_markdown("news")
    
    # 4. README 업데이트
    collector.update_readme(".")
    
    print("\n✨ 완료!")


if __name__ == "__main__":
    main()
