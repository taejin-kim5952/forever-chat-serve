---
title: 공지사항·포럼·FAQ·Q&A 게시판
category: 커뮤니티 > 게시판
url: /apidev/bbs/notice/mvNoticeList.do
related: [개발지원-문의와-테스트데이터, 포털-전체개요, 파일-업로드와-다운로드]
updated: 2026-08-15
---

# 공지사항·포럼·FAQ·Q&A 게시판

포털에는 네 종류의 게시판이 있습니다. 성격이 다르므로 글을 올릴 곳을 헷갈리지 않는
것이 중요합니다.

| 게시판 | 경로 | 성격 |
|---|---|---|
| 공지사항 | `/apidev/bbs/notice` | 운영자가 알리는 사항. 일반 사용자는 읽기만 |
| 포럼 | `/apidev/bbs/forum` | 자유 게시판. 댓글 가능 |
| FAQ | `/apidev/faq` | 자주 묻는 질문 모음 |
| Q&A | `/apidev/qna` | 질문 등록 → 담당자 답변 |

네 게시판 모두 목록·상세는 **로그인 없이** 볼 수 있습니다. 글쓰기와 댓글은 로그인이
필요합니다.

## 공지사항

| 기능 | URL |
|---|---|
| 목록 | `/bbs/notice/mvNoticeList.do` |
| 목록 데이터 | `/bbs/notice/selNoticeListAjax.do` |
| 상세 | `/bbs/notice/mvNoticeView.do` |

상단 고정(공지) 글은 목록 맨 위에 항상 표시됩니다. 첨부파일이 있으면 상세 화면에서
내려받을 수 있습니다.

## 포럼

| 기능 | URL |
|---|---|
| 목록 | `/bbs/forum/mvForumList.do` |
| 목록 데이터 | `/bbs/forum/selForumListAjax.do` |
| 상세 | `/bbs/forum/mvForumView.do` |
| 등록 화면 | `/bbs/forum/mvForumReg.do` |
| 저장 | `/bbs/forum/saveForum.do` |
| 댓글 저장 | `/bbs/forum/saveForumCommentAjax.do` |
| 댓글 삭제 | `/bbs/forum/delForumCommentAjax.do` |
| 글 삭제 | `/bbs/forum/delForumAjax.do` |

댓글은 글 상세 화면 아래에서 바로 달 수 있고, 본인이 쓴 댓글만 삭제됩니다.

## FAQ

| 기능 | URL |
|---|---|
| 목록 | `/faq/mvfaqList.do` |
| 목록 데이터 | `/faq/mvfaqListAjax.do` |
| 카테고리 조회 | `/faq/faqCateAjax.do` |
| 인기 FAQ | `/faq/mvfaqTopListAjax.do` |
| 조회수 증가 | `/faq/upRCntAjax.do` |

FAQ는 카테고리로 분류되고, 조회수가 많은 항목이 "인기 FAQ"로 상단에 노출됩니다.
질문을 펼치면 조회수가 1 올라갑니다.

## Q&A

| 기능 | URL |
|---|---|
| 목록 | `/qna/mvQnAList.do` |
| 목록 데이터 | `/qna/selQnaListAjax.do` |
| 상세 | `/qna/mvQnaView.do` |
| 등록 화면 | `/qna/mvQnaReg.do` |
| 저장 | `/qna/saveQna.do` |
| 삭제 | `/qna/delQnaAjax.do` |

Q&A는 질문을 올리면 담당자가 답변을 다는 구조입니다. 답변이 달리면 상태가 "답변
완료"로 바뀝니다. 비공개 질문으로 등록하면 작성자와 담당자만 내용을 볼 수 있습니다.

## 첨부파일

게시판 글에는 파일을 첨부할 수 있습니다. 업로드 제한은 파일 하나당 10MB, 요청 전체
10MB 입니다. 다운로드는 `/apidev/file/fileDownLoad.do` 로 처리되며 다운로드 횟수가
기록됩니다.

## 자주 묻는 질문

**Q. 질문은 어디에 올려야 하나요?**
A. API 사용 중 막힌 것이라면 Q&A, 개발 환경·테스트데이터 요청이라면 개발지원 게시판,
자유로운 논의는 포럼입니다. 답이 이미 있을 수 있으니 FAQ를 먼저 검색해 보세요.

**Q. 공지사항에 글을 쓰고 싶습니다.**
A. 운영자 권한이 있어야 합니다. 일반 사용자는 읽기만 가능합니다.

**Q. 올린 글을 지우고 싶습니다.**
A. 본인이 작성한 글만 삭제됩니다. 이미 답변이 달린 Q&A는 담당자에게 문의하세요.

**Q. 첨부파일이 안 올라갑니다.**
A. 10MB 제한을 넘었을 가능성이 큽니다. 압축하거나 나눠서 올리세요.

**Q. 비공개로 올린 질문을 다른 사람이 볼 수 있나요?**
A. 작성자와 담당자만 볼 수 있습니다. 목록에는 제목이 잠금 표시와 함께 나타납니다.
