---
id: 0032-sink-sources
title: The sources allowed to fill a sink path are listed
status: active
date: 2026-10-24
tags: [practice-packs, governance, security]
track: process
accepted-by: Sergey Strebulaev
go-getter:
  sink-sources: ""
  generated-by: restricted-data@0.6.0
  pack-answer: sink-sources
  pack-option: []
---

## Decision

`go-getter secret put` may fill a sink path only from standard input or from the declared sources [], each for its own pattern (pack restricted-data@0.6.0); the agent names a source and never supplies a command.

## Why

A secret manager with a command-line tool is reached through a declared command, with no platform code and no keychain (decision 0107).
