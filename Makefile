.PHONY: venv install validate smoke narration radio keyframes shots-fallback music-fallback \
        assemble film test clean clean-cache

PYTHON := venv/bin/python

venv:
	python3 -m venv venv

install: venv
	$(PYTHON) -m pip install -q -r requirements.txt

validate:
	$(PYTHON) -m pipeline validate

smoke:
	$(PYTHON) -m pipeline smoke

narration:
	$(PYTHON) -m pipeline narration

radio: narration
	$(PYTHON) -m pipeline radio

keyframes:
	$(PYTHON) -m pipeline keyframes

shots-fallback: narration keyframes
	$(PYTHON) -m pipeline shots --fallback

music-fallback: narration
	$(PYTHON) -m pipeline music --fallback

assemble:
	$(PYTHON) -m pipeline assemble

# The whole no-GPU path: storyboard -> narration -> keyframes -> Ken Burns
# clips -> placeholder score -> final cut, in both aspect ratios. This is
# what `make film` produces without a Kaggle GPU session; see
# notebooks/wan_shots.ipynb and notebooks/ace_step_music.ipynb for the real
# Wan 2.2 / ACE-Step path (`shots --import-dir` / `music --import-dir`),
# after which just re-run `make assemble`.
film: validate narration radio keyframes shots-fallback music-fallback assemble
	@echo "Film assembled: outputs/final/9x16.mp4 and outputs/final/16x9.mp4"

test:
	$(PYTHON) -m pytest -q

# Removes only the assemble stage's working directory (intermediate segments
# and mixes) - outputs/final/*.mp4 and every other stage's cache are left
# alone, since those are expensive (API/GPU) to regenerate.
clean-cache:
	rm -rf outputs/assemble

# Removes every generated output, including runs.jsonl's history. Source
# files (storyboard.json, schema/, notebooks/, pipeline/) are never touched.
clean:
	rm -rf outputs runs.jsonl
