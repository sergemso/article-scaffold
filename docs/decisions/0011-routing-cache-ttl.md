---
id: 0011-routing-cache-ttl
title: The prompt cache lives one hour in the main session and five minutes in subagents
status: active
date: 2026-10-24
tags: [practice-packs, model-routing, cost]
track: process
accepted-by: Sergey Strebulaev
go-getter:
  cache-ttl:
    main: 1h
    subagent: 5m
  generated-by: cost-routing@0.2.0
  pack-answer: cache-ttl
  pack-option: main-1h-sub-5m
---

## Decision

Where the host has settings for it, `apply` sets the main-session prompt-cache lifetime to one hour and subagents to five minutes (pack cost-routing@0.2.0).

## Why

A one-hour write pays off after two reads and survives pauses (fact 0011); subagents are short-lived.
