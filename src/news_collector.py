#!/usr/bin/env python3
"""
금융IT 뉴스 자동 수집 & 분석기
- RSS 피드에서 경제/IT 뉴스 수집
- 금융IT 관련 키워드로 필터링
- Gemini API로 기사 분석 및 정리
- 마크다운 파일로 저장
"""

import feedparser
import re
import os
import time
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
import google.generativeai as genai


@dataclass
class Article:
    title: str
    link: str
    summary: str
    source: str
    published: Optional[str] = None
    analyzed_content: Optional[str] = None


class FinTechNewsAnalyzer:
    """금융IT 뉴스 수집 및 분석기"""
    
    # RSS 피드 소스
    RSS_FEEDS = {
        "한국경제": "https://www.hankyung.com/feed/finance",
        "매일경제": "https://www.mk.co.kr/rss/30100041/",
        "연합뉴스_경제": "https://www.yonhapnewstv.co.kr/category/news/economy/feed/",
        "지디넷코리아": "https://www.zdnet.co.kr/rss/news.xml",
        "IT조선": "http://it.chosun.com/rss/rss.xml",
        "전자신문": "https://rss.etnews.com/Section901.xml",
    }
    
    # 금융IT 관련 키워드
    KEYWORDS = [
        # 금융 인프라
        "코어뱅킹", "차세대", "금융 클라우드", "클라우드 전환", "레거시",
        "금융 시스템", "전산 시스템", "DR센터", "재해복구", "금융 플랫폼",
        # 디지털 금융
        "오픈뱅킹", "마이데이터", "핀테크", "디지털 전환", "DX",
        "간편결제", "모바일뱅킹", "인터넷뱅킹", "네오뱅크", "챌린저뱅크",
        "CBDC", "디지털화폐", "토큰증권", "STO",
        # 금융 기술
        "금융 API", "오픈API", "금융 AI", "로보어드바이저", "챗봇",
        "블록체인", "분산원장", "RPA", "금융 데이터",
        # 보안/규제
        "금융보안", "전자금융", "금융위", "금감원", "FDS", "이상거래",
        "개인정보", "정보보호", "망분리", "제로트러스트", "금융규제",
        # 금융권 동향
        "은행 IT", "금융권 개발", "농협은행", "KB국민", "신한은행",
        "우리은행", "하나은행", "카카오뱅크", "토스뱅크",
        "금융공동망", "금융결제원", "코스콤",
        # ESG
        "녹색금융", "ESG", "탄소금융", "지속가능금융", "그린본드",
    ]
    
    # Gemini 프롬프트
    ANALYSIS_PROMPT = """다음 금융IT 관련 뉴스 기사를 분석해서 아래 형식으로 정리해줘.
반드시 마크다운 형식을 지켜줘.

[기사 제목]: {title}
[기사 출처]: {source}
[기사 내용]: {content}

---

아래 형식으로 작성해줘:

## 📋 기본 정보

| 항목 | 내용 |
|------|------|
| **날짜** | {date} |
| **출처** | {source} |
| **카테고리** | (금융규제/핀테크/금융보안/디지털금융/금융인프라 중 해당하는 것) |

---

## 📝 3줄 요약

1. (첫 번째 핵심 내용)
2. (두 번째 핵심 내용)
3. (세 번째 핵심 내용)

---

## 🔑 핵심 키워드

`키워드1` `키워드2` `키워드3` `키워드4` `키워드5`

---

## 📊 주요 내용

(기사의 핵심 내용을 표나 bullet point로 구조화해서 정리)

---

## 📖 금융 용어 정리

| 용어 | 설명 |
|------|------|
| (기사에 나온 금융/IT 전문용어) | (간단한 설명) |

(용어가 3개 이상 있으면 모두 정리, 없으면 생략)
"""

    def __init__(self):
        self.articles: list[Article] = []
        self.filtered_articles: list[Article] = []
        
        # Gemini API 설정
        api_key = os.environ.get("GEMINI_API_KEY")
        if api_key:
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel("gemini-2.0-flash")
            print("✅ Gemini API 연결됨")
        else:
            self.model = None
            print("⚠️ GEMINI_API_KEY 없음 - 기사 분석 건너뜀")
    
    def fetch_all_feeds(self) -> None:
        """모든 RSS 피드에서 뉴스 수집"""
        print("\n📰 뉴스 수집 시작...")
        
        for source_name, feed_url in self.RSS_FEEDS.items():
            try:
                feed = feedparser.parse(feed_url)
                count = 0
                
                for entry in feed.entries[:30]:
                    article = Article(
                        title=self._clean_text(entry.get("title", "")),
                        link=entry.get("link", ""),
                        summary=self._clean_text(
                            entry.get("summary", entry.get("description", ""))
                        )[:500],
                        source=source_name,
                        published=entry.get("published", entry.get("updated", ""))
                    )
                    
                    if article.title and article.link:
                        self.articles.append(article)
                        count += 1
                
                print(f"  ✓ {source_name}: {count}개 수집")
                
            except Exception as e:
                print(f"  ✗ {source_name}: 수집 실패 - {e}")
        
        print(f"📊 총 {len(self.articles)}개 기사 수집 완료")
    
    def filter_by_keywords(self) -> None:
        """금융IT 키워드로 기사 필터링"""
        print("\n🔍 금융IT 키워드 필터링 중...")
        
        seen_links = set()
        
        for article in self.articles:
            if article.link in seen_links:
                continue
            
            text = f"{article.title} {article.summary}".lower()
            
            for keyword in self.KEYWORDS:
                if keyword.lower() in text:
                    self.filtered_articles.append(article)
                    seen_links.add(article.link)
                    break
        
        print(f"📊 금융IT 관련 기사 {len(self.filtered_articles)}개 필터링 완료")
    
    def analyze_articles(self, max_articles: int = 5) -> None:
        """Gemini API로 기사 분석"""
        if not self.model:
            print("\n⚠️ Gemini API 키가 없어 분석을 건너뜁니다.")
            return
        
        print(f"\n🤖 상위 {max_articles}개 기사 AI 분석 중...")
        
        today = datetime.now().strftime("%Y.%m.%d")
        
        for i, article in enumerate(self.filtered_articles[:max_articles]):
            try:
                print(f"  분석 중 ({i+1}/{max_articles}): {article.title[:40]}...")
                
                prompt = self.ANALYSIS_PROMPT.format(
                    title=article.title,
                    source=article.source,
                    content=article.summary,
                    date=today
                )
                
                response = self.model.generate_content(prompt)
                article.analyzed_content = response.text
                
                # API 속도 제한 대응 (무료 티어: 분당 15회)
                time.sleep(4)
                
            except Exception as e:
                print(f"    ✗ 분석 실패: {e}")
                article.analyzed_content = None
        
        analyzed_count = sum(1 for a in self.filtered_articles[:max_articles] if a.analyzed_content)
        print(f"📊 {analyzed_count}개 기사 분석 완료")
    
    def generate_markdown(self, output_dir: str = "news") -> str:
        """마크다운 파일 생성"""
        today = datetime.now()
        filename = f"{today.strftime('%Y-%m-%d')}.md"
        filepath = Path(output_dir) / filename
        
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        content = self._build_markdown_content(today)
        filepath.write_text(content, encoding="utf-8")
        
        print(f"\n✅ 마크다운 파일 생성: {filepath}")
        return str(filepath)
    
    def _build_markdown_content(self, date: datetime) -> str:
        """마크다운 컨텐츠 빌드"""
        lines = [
            f"# 🏦 금융IT 뉴스 스크랩 | {date.strftime('%Y년 %m월 %d일')}",
            "",
            f"> 자동 수집 시간: {date.strftime('%Y-%m-%d %H:%M')} KST",
            "",
            "---",
            "",
            "## 📊 오늘의 요약",
            "",
            f"- 총 수집 기사: {len(self.articles)}개",
            f"- 금융IT 관련: {len(self.filtered_articles)}개",
            f"- AI 분석 완료: {sum(1 for a in self.filtered_articles if a.analyzed_content)}개",
            "",
            "---",
            "",
        ]
        
        # AI 분석된 기사
        for i, article in enumerate(self.filtered_articles):
            if article.analyzed_content:
                lines.extend([
                    f"# {i+1}. [{article.title}]({article.link})",
                    "",
                    article.analyzed_content,
                    "",
                    "---",
                    "",
                ])
        
        # 분석 안 된 나머지 기사 (간단히 목록으로)
        remaining = [a for a in self.filtered_articles if not a.analyzed_content]
        if remaining:
            lines.extend([
                "## 📰 기타 금융IT 뉴스",
                "",
            ])
            for article in remaining[:10]:
                lines.append(f"- [{article.title}]({article.link}) - {article.source}")
            lines.extend(["", "---", ""])
        
        # 푸터
        lines.extend([
            "",
            "*이 문서는 GitHub Actions + Gemini API로 자동 생성되었습니다.*",
        ])
        
        return "\n".join(lines)
    
    @staticmethod
    def _clean_text(text: str) -> str:
        """HTML 태그 및 특수문자 정리"""
        text = re.sub(r"<[^>]+>", "", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()


def main():
    print("=" * 50)
    print("🏦 금융IT 뉴스 자동 수집 & 분석기")
    print("=" * 50)
    
    analyzer = FinTechNewsAnalyzer()
    
    # 1. 뉴스 수집
    analyzer.fetch_all_feeds()
    
    # 2. 키워드 필터링
    analyzer.filter_by_keywords()
    
    # 3. AI 분석 (상위 5개)
    analyzer.analyze_articles(max_articles=5)
    
    # 4. 마크다운 생성
    analyzer.generate_markdown("news")
    
    print("\n✨ 완료!")


if __name__ == "__main__":
    main()
