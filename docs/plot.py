"""python docs/plot.py  -> docs/result.png from out/heldout.json"""
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

r = json.load(open("out/heldout.json"))
n = r["worlds"]
fig, ax = plt.subplots(1, 2, figsize=(11, 4.2))
w = r["wrong_winner"]
labels = ["peak of 5\n(one sitting)", "median of 5\n(one sitting)", "protocol\n(30 runs, 3 sessions)"]
vals = [w["peak_of_5"], w["median_of_5"], w["harness_30_runs_3_sessions"]]
b = ax[0].bar(labels, vals, color=["#c0397a", "#c98500", "#292e93"])
ax[0].bar(labels[2], r["harness_says_tie"], bottom=vals[2], color="#c3cad6", label='"tie" (no winner named)')
for bar, v in zip(b, vals):
    ax[0].text(bar.get_x() + bar.get_width() / 2, v + 2, str(v), ha="center", fontweight="bold")
ax[0].set_title(f"Wrong winner named, {n} held-out 3-provider worlds")
ax[0].legend(frameon=False, loc="upper left")
o = r["overstatement_vs_true_median_pct"]
lab2 = ["peak of 5", "peak of 30", "median of 5", "protocol median"]
v2 = [o["peak5"], o["peak30"], o["median5"], o["harness30"]]
b2 = ax[1].bar(lab2, v2, color=["#c0397a", "#e0632f", "#c98500", "#292e93"])
for bar, v in zip(b2, v2):
    ax[1].text(bar.get_x() + bar.get_width() / 2, v + 1.5, f"{v:+.1f}%", ha="center", fontweight="bold")
ax[1].set_title("Reported decode speed vs true typical (median) speed")
ax[1].set_ylabel("% above truth")
for a in ax:
    a.spines[["top", "right"]].set_visible(False)
fig.tight_layout()
fig.savefig("docs/result.png", dpi=130)
