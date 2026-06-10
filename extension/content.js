let hoveredButton = null;

document.addEventListener("mouseover", (e) => {
  const button = e.target.closest("button");
  if (button) {
    hoveredButton = button;
  }
});

document.addEventListener("mouseout", (e) => {
  const button = e.target.closest("button");
  if (button && button === hoveredButton) {
    hoveredButton = null;
  }
});

document.addEventListener("keydown", async (e) => {
  if (e.ctrlKey && e.shiftKey && (e.key === "L" || e.key === "l")) {
    e.preventDefault();
    showSetupMenu();
    return;
  }

  if (!(e.ctrlKey && e.shiftKey && (e.key === "E" || e.key === "e"))) return;
  if (!hoveredButton) return;

  e.preventDefault();

  const button = hoveredButton;
  const requestId = `codelens-${Date.now()}-${Math.random().toString(36).slice(2)}`;
  const context = {
    testid: button.getAttribute("data-testid") || "",
    label:
      (button.innerText || "").trim() ||
      button.getAttribute("aria-label") ||
      button.title ||
      "",
    route: window.location.pathname,
    request_id: requestId,
    // Icon-only buttons have no label — give the agent the markup and the
    // surrounding row text so it can still identify the button.
    html: button.outerHTML.slice(0, 600),
    surrounding_text: (
      button.closest("li, tr, article, [class*='task'], [class*='card'], [class*='row']") || button.parentElement || button
    ).innerText
      .trim()
      .slice(0, 200),
  };

  const controller = new AbortController();
  const cancelAnalysis = () => {
    controller.abort();
    fetch("http://localhost:8000/cancel", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ request_id: requestId }),
    }).catch(() => {});
  };

  showPanel(button, null, true, cancelAnalysis);

  try {
    const response = await fetch("http://localhost:8000/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(context),
      signal: controller.signal,
    });
    const data = await response.json();
    showPanel(button, data, false);
  } catch (err) {
    if (err.name === "AbortError") return;
    showPanel(
      button,
      { error: "Backend not reachable. Is the FastAPI server running on port 8000?" },
      false
    );
  }
});
