#!/usr/bin/env python3
"""
금융IT 뉴스 자동 수집 & 분석기
- RSS 피드에서 경제/IT 뉴스 수집
- 금융IT 관련 키워드로 필터링
- Groq API로 기사 분석 및 정리
- 마크다운 파일로 저장
"""

import feedparser
import requests
import re
import os
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
from newspaper import Article as NewsArticle

# 한국 시간대 (UTC+9)
KST = timezone(timedelta(hours=9))


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
    
    # 금융IT 관련 키워드 (기사 필터링용)
    KEYWORDS = [
        # 금융 인프라
        "코어뱅킹", "차세대 시스템", "차세대", "금융 클라우드", "클라우드 전환", 
        "레거시", "전산장애", "DR센터", "재해복구", "금융 플랫폼",
        "IT 아웃소싱", "데이터센터", "시스템 통합", "SI",
        # 디지털 금융
        "오픈뱅킹", "마이데이터", "핀테크", "디지털 전환", "DX",
        "간편결제", "모바일뱅킹", "인터넷뱅킹", "네오뱅크", "챌린저뱅크",
        "CBDC", "디지털화폐", "토큰증권", "STO", "디지털자산",
        "슈퍼앱", "빅테크", "테크핀",
        # 금융 기술
        "금융 API", "오픈API", "금융 AI", "로보어드바이저", "AI 심사",
        "블록체인", "분산원장", "RPA", "실시간 처리", "대용량 처리",
        "빅데이터", "MSA", "마이크로서비스",
        # 보안/규제
        "금융보안", "전자금융", "금융위", "금감원", "FDS", "이상거래",
        "개인정보", "정보보호", "망분리", "제로트러스트", "금융규제",
        "보이스피싱", "스미싱", "금융사기", "자금세탁", "AML",
        # 금융권 (주요 기관)
        "은행 IT", "금융권 개발", "금융결제원", "코스콤", "금융공동망", "예탁결제원",
        "농협은행", "NH농협", "농협금융", "NH투자증권",
        "KB국민", "신한은행", "우리은행", "하나은행", 
        "카카오뱅크", "토스뱅크", "케이뱅크",
        # ESG/기타
        "녹색금융", "ESG금융", "ESG", "탄소금융", "그린본드",
    ]
    
    # AI 분석 프롬프트
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

## 💡 핵심 요약

> (기사의 핵심을 한 문장으로 정리. 구체적인 수치, 인물명, 정책명 포함)

---

## 🔑 키워드

`키워드1` `키워드2` `키워드3` `키워드4` `키워드5`

---

## 📊 주요 내용

### 배경
- (이 사안이 나오게 된 배경이나 맥락)

### 핵심 사안
- (기사에서 가장 중요한 내용)
- (구체적인 수치, 정책, 발언 등 포함)

### 향후 전망
- (예상되는 영향이나 앞으로의 방향)

---

## 📖 금융 용어

| 용어 | 설명 |
|------|------|
| (기사에 나온 금융/IT 전문용어) | (간단한 설명) |

(전문용어가 없으면 이 섹션 생략)
"""

    def __init__(self):
        self.articles: list[Article] = []
        self.filtered_articles: list[Article] = []
        
        # Groq API 설정
        self.api_key = os.environ.get("GROQ_API_KEY")
        if self.api_key:
            print("✅ Groq API 연결됨")
        else:
            print("⚠️ GROQ_API_KEY 없음 - 기사 분석 건너뜀")
    
    def fetch_all_feeds(self) -> None:
        """모든 RSS 피드에서 뉴스 수집"""
        print("\n📰 뉴스 수집 시작...")
        
        # 24시간 이내 기사만 수집
        now = datetime.now(KST)
        cutoff = now - timedelta(hours=24)
        print(f"  📅 수집 범위: {cutoff.strftime('%m/%d %H:%M')} ~ {now.strftime('%m/%d %H:%M')}")
        
        for source_name, feed_url in self.RSS_FEEDS.items():
            try:
                feed = feedparser.parse(feed_url)
                count = 0
                
                for entry in feed.entries[:30]:
                    # 24시간 이내 기사만 필터링
                    published_datetime = self._parse_datetime(entry)
                    if not published_datetime or published_datetime < cutoff:
                        continue
                    
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
        
        print(f"📊 총 {len(self.articles)}개 기사 수집 완료 (최근 24시간)")
    
    def _parse_datetime(self, entry) -> Optional[datetime]:
        """RSS 엔트리에서 datetime 파싱"""
        try:
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                return datetime(*entry.published_parsed[:6], tzinfo=KST)
            if hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                return datetime(*entry.updated_parsed[:6], tzinfo=KST)
        except Exception:
            pass
        return None
    
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
        
        # 중요도 점수로 정렬
        self._rank_articles()
    
    def _rank_articles(self) -> None:
        """기사 중요도 점수 계산 및 정렬"""
        print("\n📈 기사 중요도 분석 중...")
        
        # 핵심 키워드 (금융IT 핵심 주제)
        core_keywords = [
            # 규제/감독 기관
            "금감원", "금융위", "금융규제", "전자금융", "금융정책",
            # 금융 인프라/시스템
            "코어뱅킹", "차세대", "금융 클라우드", "레거시", "전산장애",
            # 디지털 금융 정책
            "오픈뱅킹", "마이데이터", "CBDC", "디지털화폐", "토큰증권",
            # 보안
            "금융보안", "FDS", "이상거래", "망분리", "보이스피싱",
            # 핵심 트렌드
            "핀테크", "디지털 전환", "금융 API", "빅테크",
            # 주요 금융사 (타겟: 농협)
            "농협은행", "NH농협", "농협금융",
            "KB국민", "신한은행", "우리은행", "하나은행",
            "카카오뱅크", "토스뱅크", "케이뱅크",
            # 금융 인프라 기관
            "금융결제원", "코스콤", "금융공동망", "예탁결제원",
        ]
        
        scored_articles = []
        
        for article in self.filtered_articles:
            score = 0
            title_lower = article.title.lower()
            text_lower = f"{article.title} {article.summary}".lower()
            
            # 1. 제목에 키워드 포함 +3점/개
            for keyword in self.KEYWORDS:
                if keyword.lower() in title_lower:
                    score += 3
            
            # 2. 핵심 키워드 매칭 +2점/개
            for keyword in core_keywords:
                if keyword.lower() in text_lower:
                    score += 2
            
            # 3. 일반 키워드 매칭 +1점/개
            for keyword in self.KEYWORDS:
                if keyword.lower() in text_lower:
                    score += 1
            
            scored_articles.append((score, article))
        
        # 점수 높은 순으로 정렬
        scored_articles.sort(key=lambda x: x[0], reverse=True)
        
        # 유사 기사 중복 제거
        deduplicated = self._remove_similar_articles(scored_articles)
        self.filtered_articles = deduplicated
        
        # 상위 5개 점수 출력
        print("  🏆 중요도 TOP 5 (중복 제거 후):")
        for i, article in enumerate(self.filtered_articles[:5]):
            print(f"     {i+1}. {article.title[:45]}...")
    
    def _remove_similar_articles(self, scored_articles: list) -> list:
        """유사한 기사 중복 제거"""
        selected = []
        selected_titles = []
        
        for score, article in scored_articles:
            # 제목에서 핵심 단어 추출 (2글자 이상)
            title_words = set(
                word for word in re.split(r'[\s\[\]…·""\'\'\",\-\_\(\)]', article.title)
                if len(word) >= 2
            )
            
            # 이미 선택된 기사들과 유사도 체크
            is_similar = False
            for prev_words in selected_titles:
                if not title_words or not prev_words:
                    continue
                
                # 1. 정확히 일치하는 단어 개수
                exact_match = len(title_words & prev_words)
                
                # 2. 부분 문자열 매칭 (인지수사권 vs 인지수사 등)
                partial_match = 0
                for word1 in title_words:
                    for word2 in prev_words:
                        if word1 != word2 and len(word1) >= 2 and len(word2) >= 2:
                            if word1 in word2 or word2 in word1:
                                partial_match += 1
                                break
                
                # 부분 매칭도 정확히 일치와 동일하게 1점
                total_match = exact_match + partial_match
                similarity = total_match / min(len(title_words), len(prev_words))
                
                # 유사도 40% 이상이면 중복으로 판단
                if similarity >= 0.4:
                    is_similar = True
                    break
            
            if not is_similar:
                selected.append(article)
                selected_titles.append(title_words)
        
        removed_count = len(scored_articles) - len(selected)
        if removed_count > 0:
            print(f"  🔄 유사 기사 {removed_count}개 중복 제거")
        
        return selected
    
    def _fetch_full_content(self, url: str) -> Optional[str]:
        """기사 원문 스크래핑"""
        try:
            news = NewsArticle(url, language='ko')
            news.download()
            news.parse()
            
            if news.text and len(news.text) > 100:
                # 너무 길면 앞부분만 사용 (약 3000자)
                return news.text[:3000]
            return None
        except Exception:
            return None
    
    def analyze_articles(self, max_articles: int = 5) -> None:
        """Groq API로 기사 분석"""
        if not self.api_key:
            print("\n⚠️ Groq API 키가 없어 분석을 건너뜁니다.")
            return
        
        print(f"\n🤖 상위 {max_articles}개 기사 AI 분석 중...")
        
        # 실행일 기준
        today = datetime.now(KST).strftime("%Y.%m.%d")
        
        for i, article in enumerate(self.filtered_articles[:max_articles]):
            try:
                print(f"  분석 중 ({i+1}/{max_articles}): {article.title[:40]}...")
                
                # 원문 스크래핑 시도
                full_content = self._fetch_full_content(article.link)
                if full_content:
                    content = full_content
                    print(f"    ✓ 원문 {len(content)}자 수집")
                else:
                    content = article.summary
                    print(f"    → RSS 요약 사용")
                
                prompt = self.ANALYSIS_PROMPT.format(
                    title=article.title,
                    source=article.source,
                    content=content,
                    date=today
                )
                
                # API 호출 (429 에러 시 재시도)
                max_retries = 3
                for attempt in range(max_retries):
                    response = requests.post(
                        "https://api.groq.com/openai/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json"
                        },
                        json={
                            "model": "llama-3.1-8b-instant",
                            "messages": [{"role": "user", "content": prompt}],
                            "temperature": 0.3,
                            "max_tokens": 2000
                        },
                        timeout=60
                    )
                    
                    if response.status_code == 429:
                        wait_time = 30 * (attempt + 1)
                        print(f"    ⏳ 속도 제한, {wait_time}초 대기 후 재시도...")
                        time.sleep(wait_time)
                        continue
                    
                    response.raise_for_status()
                    break
                
                result = response.json()
                article.analyzed_content = result["choices"][0]["message"]["content"]
                
                # API 속도 제한 대응 (원문 분석 시 토큰 많이 사용)
                time.sleep(10)
                
            except Exception as e:
                print(f"    ✗ 분석 실패: {e}")
                article.analyzed_content = None
        
        analyzed_count = sum(1 for a in self.filtered_articles[:max_articles] if a.analyzed_content)
        print(f"📊 {analyzed_count}개 기사 분석 완료")
    
    def generate_markdown(self, output_dir: str = "news") -> str:
        """마크다운 파일 생성"""
        # 실행일 기준
        today = datetime.now(KST)
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
            "*이 문서는 GitHub Actions + Groq API로 자동 생성되었습니다.*",
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
