---
title: 애플리케이션 - 팀 단위 API 관리와 연동 유형
category: API Link 포털 > 애플리케이션
source_files: [kt_API_Link_서비스소개서.pdf]
updated: 2026-10-07
---

# 애플리케이션 - 팀 단위 API 관리와 연동 유형

API Link 는 애플리케이션 단위로 멤버 · 구독 API · IP · Key 를 통합 관리합니다. 애플리케이션은 목적에 따라 API · MCP · OAuth 세 가지 유형으로 만듭니다.

## 애플리케이션이란 무엇인가

질문: 애플리케이션이 뭔가요 / 왜 애플리케이션을 만들어야 하나요 / 애플리케이션 단위 관리 / 팀 단위 관리

애플리케이션은 **팀이 함께 API 를 관리하는 단위**입니다. 연동에 필요한 정보를 애플리케이션 하나로 묶습니다.

- **멤버** - 이 애플리케이션을 함께 관리하는 사람들
- **구독 API** - 이 애플리케이션이 쓰는 KT API 와 승인 상태
- **IP Whitelist** - API 를 호출할 서버의 IP 를 DEV · PRD 환경별로 등록
- **API Key** - DEV · PRD 환경별로 발급되는 인증 Key

구독 API · IP · Key · 담당자를 따로 관리하지 않고 한 곳에서 보므로, 담당자가 바뀌어도 연동 정보가 흩어지지 않습니다.

## 멤버 역할 - Owner 와 Manager

질문: Owner 와 Manager 차이 / 담당자 자동 지정이 뭔가요 / 멤버 역할 / 애플리케이션 관리자는 누구인가요

애플리케이션 멤버는 역할로 구분되며, 주요 담당자는 자동으로 지정됩니다.

- **Owner** - 애플리케이션을 만든 사람입니다.
- **Manager** - 애플리케이션의 승인 요청을 처리하는 역할입니다.

담당자는 **자동으로 지정**됩니다. 애플리케이션을 만들 때 담당자를 따로 찾아 등록하지 않아도 됩니다.

## 구독 API 와 승인

질문: API 구독이 뭔가요 / 구독하면 바로 쓸 수 있나요 / 민감 API 는 왜 승인이 필요한가요 / 자동 승인 / 구독 승인 상태

애플리케이션에서 사용할 KT API 를 고르는 것을 **구독**이라고 합니다. API 마다 구독 승인 요청과 상태를 애플리케이션 안에서 한 번에 확인합니다.

- **일반 API** - 자동으로 승인됩니다.
- **민감 파라미터가 포함된 API** - 개인정보 같은 민감정보를 다루므로, 이용 사유를 적어 신청하고 관리자 승인을 받은 뒤 이용할 수 있습니다.

## IP Whitelist 와 API Key

질문: IP Whitelist 가 뭔가요 / 왜 IP 를 등록해야 하나요 / API Key 는 어떻게 받나요 / DEV Key 와 PRD Key 차이

API Link 는 **등록된 서버에서, 발급된 Key 로** 호출할 때만 구독 API 를 이용하게 합니다.

- **IP Whitelist** - API 를 호출할 서버의 IP 를 DEV · PRD 환경별로 등록합니다. 개발 환경 IP 는 바로 쓸 수 있고, 운영 환경(PRD) IP 는 승인을 거쳐 등록됩니다.
- **API Key** - DEV Key 와 PRD Key 가 분리 발급됩니다. DEV Key 로 개발 · 테스트를 하고, PRD Key 는 상용 전환 후 자동으로 발급됩니다. Key 에는 만료일이 있어 화면에서 만료일을 확인하고 복사해 씁니다.

## 연동 유형 세 가지 - API · MCP · OAuth

질문: 애플리케이션 유형은 뭐가 있나요 / API MCP OAuth 차이 / 어떤 유형을 골라야 하나요 / 연동 방식 종류

애플리케이션은 연동 목적에 따라 세 가지 유형으로 만듭니다.

- **API Application** - KT REST API 를 구독하고 Key 로 호출하는 연동입니다. 가장 일반적인 유형입니다.
- **MCP Application** - 고객의 AI Agent 가 MCP(Model Context Protocol)로 KT 서비스 Tool 을 호출하도록 연결하는 연동입니다. 오픈 예정이며, 세부 사항은 오픈 시 안내됩니다.
- **OAuth Application** - 고객 서비스의 사용자가 KT 계정으로 로그인하도록 OAuth 2.0 으로 연결하는 연동입니다.

## API Application 의 호출 방식

질문: API Application 은 어떻게 호출하나요 / KT REST API 호출 구조 / 호출할 때 무엇을 확인하나요 / API Application 설정 순서

API Application 은 고객 서버가 **Whitelist 에 등록된 IP** 에서 **API Key** 를 붙여 구독한 KT REST API 를 호출하는 방식입니다. 호출할 때 API Link 가 등록된 IP 인지와 API Key 를 확인한 뒤 KT REST API(DEV 또는 PRD)로 전달합니다.

설정은 다음 순서로 진행합니다.

1. 사용할 KT API 를 구독 신청합니다.
2. DEV · PRD 호출 서버 IP 를 IP Whitelist 에 등록합니다.
3. API Key 를 발급받습니다. DEV Key 로 테스트하고, PRD Key 는 상용 전환 후 자동으로 발급됩니다.

## MCP Application 과 OAuth Application

질문: MCP Application 이 뭔가요 / MCP 는 언제 쓸 수 있나요 / OAuth Application 이 뭔가요 / KT 계정으로 로그인 연동 / Redirect URL 이 뭔가요

**MCP Application** 은 고객의 AI 서비스(AI Agent)가 KT 가 제공하는 MCP Server 를 통해 KT 서비스 Tool 을 호출하도록 연결합니다. 연동할 MCP Server 와 Tool 을 고르고, 호출 서버 IP 를 등록하며, Agent 연결용 인증 정보를 발급받는 방식입니다. 현재 오픈 예정입니다.

**OAuth Application** 은 OAuth 2.0 표준 인가 코드 방식으로, 고객 서비스의 사용자가 KT 계정으로 로그인 · 동의하면 고객 서비스가 인가 코드를 받아 토큰을 발급받는 연동입니다.

- 고객 서비스는 승인 후 발급되는 **Client ID / Secret** 으로 자신을 식별합니다.
- 로그인을 마친 사용자를 되돌려 보낼 **Redirect URL** 을 등록합니다.
- 사용자에게서 받을 정보의 범위를 정합니다.
