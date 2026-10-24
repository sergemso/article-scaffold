---
id: 0041-verification-checks
title: Implement and debug steps pass the project's detected check commands
status: active
date: 2026-10-24
tags: [practice-packs, verification, harness]
track: process
accepted-by: Sergey Strebulaev
go-getter:
  verify-scope: detected
  generated-by: verification-gate@0.4.0
  pack-answer: checks
  pack-option: detected
---

## Decision

A step of class implement or debug is verified by `go-getter verify --class <class>`, which runs the commands recorded in the command decisions that the machine profile places locally; an empty command is skipped.

## Why

The quality bar of routing (decisions 0016, 0017) is these checks: a cheaper tier that passes them is as good as a dearer one, and one that fails them escalates instead of shipping (pack verification-gate@0.4.0).
