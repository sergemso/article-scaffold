---
id: 0013-confidential-data-routing
title: Confidential data may go wherever internal data may
status: active
date: 2026-10-24
tags: [practice-packs, governance, security]
track: process
accepted-by: Sergey Strebulaev
go-getter:
  data-classes:
    confidential:
      enabled: true
      requires-zdr: false
  generated-by: data-policy@0.6.0
  pack-answer: confidential-zdr
  pack-option: zdr-not-required
---

## Decision

Confidential data goes to the models internal data may go to. (pack data-policy@0.6.0).

## Why

Confidential data needs a retention guarantee only some teams have contracted (decision 0018).
