
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

jni:
	@$(PYTHON) $(TOP_DIR)$(PATCHDEV) jni

diff:
	@$(PYTHON) $(TOP_DIR)$(PATCHDEV) diff

patch:
	@$(PYTHON) $(TOP_DIR)$(PATCHDEV) patch

check:
	@$(PYTHON) $(TOP_DIR)$(PATCHDEV) check

clean:
	@$(PYTHON) $(TOP_DIR)$(PATCHDEV) clean
