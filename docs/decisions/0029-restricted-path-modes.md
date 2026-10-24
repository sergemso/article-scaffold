---
id: 0029-restricted-path-modes
title: Restricted paths have an access mode, deny unless listed
status: active
date: 2026-10-24
tags: [practice-packs, governance, security]
track: process
accepted-by: Sergey Strebulaev
go-getter:
  restricted-modes: ""
  generated-by: restricted-data@0.6.0
  pack-answer: restricted-modes
  pack-option: []
---

## Decision

A restricted path pattern listed in `go-getter.restricted-modes` as `use:<pattern>` or `sink:<pattern>` has that mode; every other one is `deny` (pack restricted-data@0.6.0). A `use` path may be passed to an approved command by a call that is exactly `go-getter secret run`, and a `sink` path may be written from a declared source by a call that is exactly `go-getter secret put`; every other call that names one is denied like a `deny` path.

## Why

Agents need secrets they can use or fill without reading them, and no other go-getter command may be the exemption, since one that runs a user-supplied command would leak the content (decision 0072).
