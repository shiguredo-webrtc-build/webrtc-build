
PYTHON = python3
TOP_DIR = ../../
PATCHDEV = scripts/patchdev.py

.PHONY: build start diff patch clean

build:
	@$(PYTHON) $(TOP_DIR)$(PATCHDEV) build

start:
	@$(PYTHON) $(TOP_DIR)$(PATCHDEV) start

diff:
	@$(PYTHON) $(TOP_DIR)$(PATCHDEV) diff

patch:
	@$(PYTHON) $(TOP_DIR)$(PATCHDEV) patch

clean:
	@$(PYTHON) $(TOP_DIR)$(PATCHDEV) clean
