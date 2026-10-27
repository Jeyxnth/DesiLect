.PHONY: doctor setup dev dev-backend dev-frontend serve-lan sample test test-backend test-frontend offline-check drill bench

# Python used to create the venv (project targets 3.11)
PYTHON ?= python
VENV   := .venv
ifeq ($(OS),Windows_NT)
VPY := $(VENV)/Scripts/python
else
VPY := $(VENV)/bin/python
endif

doctor:
	$(PYTHON) scripts/doctor.py

setup:
	$(PYTHON) -m venv $(VENV)
	$(VPY) -m pip install --upgrade pip
	$(VPY) -m pip install -r backend/requirements.txt
	cd frontend && npm install

dev:
	$(MAKE) -j2 dev-backend dev-frontend

dev-backend:
	cd backend && ../$(VPY) -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

dev-frontend:
	cd frontend && npm run dev

# The built app on every interface, for the phone check: open http://<this laptop's IP>:8000 on a phone on the
# same hotspot/LAN (no internet needed). Allow Python through the firewall when Windows asks.
serve-lan:
	cd frontend && npm run build
	cd backend && ../$(VPY) -m uvicorn app.main:app --host 0.0.0.0 --port 8000

sample:
	$(VPY) scripts/render_sample.py

test: test-backend test-frontend

test-backend:
	cd backend && ../$(VPY) -m pytest -q

test-frontend:
	cd frontend && npm run typecheck

offline-check:
	$(VPY) scripts/check_offline.py

# Step 12: 18-lesson matrix + failure drills, appended to docs/offline-test.md.
# With Wi-Fi physically off: make drill ARGS=--wifi-off   (the flag only records it in the report)
drill:
	$(VPY) scripts/drill.py $(ARGS)

bench:
	$(VPY) scripts/bench.py
