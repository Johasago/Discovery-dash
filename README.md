# 📊 Jira Agile Flow & Predictability Dashboard

An automated, cloud-hosted Agile intelligence platform built with Python and Streamlit. 

This tool bypasses the limitations of native Jira reporting by directly extracting raw API data, excluding weekends from lead time calculations, and generating enterprise-grade predictability metrics in real-time.

## 🚀 The Problem It Solves
Native Jira reports are often clunky, difficult to filter across multiple projects, and artificially inflate delivery times by counting weekends. We needed a tool that doesn't just tell us what we *did*, but tells us how *predictable* we are and where our bottlenecks are forming today.

## ✨ Key Features
* **🤖 Automated Executive Summary:** A Python-driven logic engine that reads 30-day throughput and active stalled tickets to generate a plain-English health check.
* **⚖️ Period-over-Period (PoP) Analysis:** Dynamic comparison calendars with inverse color-coded deltas (e.g., Lead Time dropping is green!).
* **⚠️ Aging WIP (Standup Tool):** A daily operational view that draws an 85th percentile "Danger Zone" line to instantly highlight stalled work.
* **🎯 Predictability Control Charts:** Scatter plots mapping historical lead times against rolling Standard Deviations.
* **📉 Coefficient of Variation (CV):** Monthly bar charts and trend lines tracking our relative predictability over time.
* **🌊 Cumulative Flow Diagram (CFD):** A custom-engineered "Time Machine" script that reconstructs daily ticket statuses using Jira's changelog API.

## 🏗️ Technical Architecture
The project is split into two halves: the **Data Pipeline** (Extractors) and the **Frontend** (Streamlit App).

### 1. The Data Pipeline
Runs locally on a cron job schedule (2:00 PM daily) to bypass corporate SSO restrictions.
* `jira_extract.py`: Pulls all Active Work In Progress.
* `lead_time_extract.py`: Pulls completed tickets and calculates true business-day lead times.
* `cfd_extract.py`: Parses the Jira changelog history to build the CFD Time Machine.
* `refresh_data.sh` / `.bat`: The master script that runs the extractors and pushes fresh CSVs to GitHub.

### 2. The Streamlit Frontend
Hosted securely in the cloud.
* `app.py`: The main application file. Uses Pandas for data transformation and Plotly for interactive, high-fidelity visualizations.

## 🛠️ Local Setup & Installation

**1. Clone the repository**
```bash
git clone [https://github.com/your-username/Discovery-dash.git](https://github.com/your-username/Discovery-dash.git)
cd Discovery-dash
