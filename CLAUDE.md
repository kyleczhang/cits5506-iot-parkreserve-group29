# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**ParkReserve** is an IoT-based smart parking monitoring and reservation system (CITS5506 university coursework, Group 29). The system uses ESP32 microcontrollers with ultrasonic/infrared sensors to detect parking occupancy, indicator LEDs (green/yellow/red), automated barriers for reserved spots, and a web dashboard — all communicating over WiFi.

**Team:** Nyx Chen, Fahim Abrar, Riya Sakhiya, Yuan Cong Yuan, Cheng Zhang

## Planned Architecture

The system has three layers:

1. **IoT Firmware** (ESP32 / Arduino C++ or MicroPython): reads sensors, controls LEDs and barriers, communicates status to backend via WiFi.
2. **Backend Server**: manages reservations, relays commands to ESP32 nodes, persists state to a database.
3. **Web/Mobile Dashboard**: lets users view real-time availability and make reservations.

Spot states: `available` (green LED) → `reserved` (yellow LED + barrier up) → `occupied` (red LED).

## Repository Status

This project is in the **proposal/planning phase** — no implementation exists yet. The repo contains only `README.md` and PDF reference documents (rubric, proposal template, sample proposal). Implementation directories (e.g. `firmware/`, `backend/`, `frontend/`) have not been created yet.

When implementation begins, update this file with actual build/run/test commands, environment variable requirements, and any hardware-specific setup notes.
