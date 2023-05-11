
PYTHON = python3
TOP_DIR = ../../
PATCHDEV = scripts/patchdev.py

.PHONY: build start diff generate clean

build:
	@$(PYTHON) $(TOP_DIR)$(PATCHDEV) build

start:
	@$(PYTHON) $(TOP_DIR)$(PATCHDEV) start

diff:
	@$(PYTHON) $(TOP_DIR)$(PATCHDEV) diff

generate:
	@$(PYTHON) $(TOP_DIR)$(PATCHDEV) generate

clean:
	@$(PYTHON) $(TOP_DIR)$(PATCHDEV) clean
