
PYTHON = python3
TOP_DIR = ../../
PATCHDEV = scripts/patchdev.py

.PHONY: sync build diff patch clean javah

sync:
	@$(PYTHON) $(TOP_DIR)$(PATCHDEV) sync

build:
	@$(PYTHON) $(TOP_DIR)$(PATCHDEV) build

build-skip-patch:
	@$(PYTHON) $(TOP_DIR)$(PATCHDEV) build --skip-patch


diff:
	@$(PYTHON) $(TOP_DIR)$(PATCHDEV) diff

patch:
	@$(PYTHON) $(TOP_DIR)$(PATCHDEV) patch

check:
	@$(PYTHON) $(TOP_DIR)$(PATCHDEV) check

clean:
	@$(PYTHON) $(TOP_DIR)$(PATCHDEV) clean

javah:
	javah -classpath src/sdk/android/api -classpath ../../_source/android/webrtc/src/sdk/android/api -o simulcast_video_encoder.h org.webrtc.SimulcastVideoEncoder
