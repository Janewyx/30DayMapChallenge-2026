"""Display the three saved Day 05 figures using the shared configuration."""

import json
from pathlib import Path
import matplotlib.pyplot as plt

DAY = Path(__file__).resolve().parents[1]
settings = json.loads((DAY / "config" / "sight.json").read_text())

for entry in settings["images"]:
    # These are finished PNGs, so no climate analysis is rerun here.
    picture = plt.imread(DAY / entry["path"])
    fig, ax = plt.subplots(figsize=(12, 10), facecolor=settings["figure_background"])
    ax.imshow(picture)
    ax.set_title(entry["title"], color=settings["text_color"], loc="left")
    ax.axis("off")
    plt.show()
