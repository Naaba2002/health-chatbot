(function () {
  const chatWindow = document.getElementById("chatWindow");
  const chatForm = document.getElementById("chatForm");
  const chatInput = document.getElementById("chatInput");
  const quickRepliesEl = document.getElementById("quickReplies");
  const resetBtn = document.getElementById("resetBtn");

  // The full conversation state lives here, in the browser, and is sent
  // back to the server on every request. The server itself keeps no memory
  // between requests -- see the note at the top of app.py for why.
  let conversationState = null;

  function addBubble(text, sender, urgency) {
    const bubble = document.createElement("div");
    bubble.className = `bubble ${sender}`;
    if (sender === "bot" && urgency === "emergency") bubble.classList.add("emergency");
    if (sender === "bot" && urgency === "urgent") bubble.classList.add("urgent");
    bubble.textContent = text;
    chatWindow.appendChild(bubble);
    chatWindow.scrollTop = chatWindow.scrollHeight;
    return bubble;
  }

  function showTyping() {
    const el = document.createElement("div");
    el.className = "typing-indicator";
    el.id = "typingIndicator";
    el.innerHTML = "<span></span><span></span><span></span>";
    chatWindow.appendChild(el);
    chatWindow.scrollTop = chatWindow.scrollHeight;
  }

  function hideTyping() {
    const el = document.getElementById("typingIndicator");
    if (el) el.remove();
  }

  function renderQuickReplies(options) {
    quickRepliesEl.innerHTML = "";
    (options || []).forEach((label) => {
      const btn = document.createElement("button");
      btn.className = "quick-reply-btn";
      btn.type = "button";
      btn.textContent = label;
      btn.addEventListener("click", () => sendMessage(label));
      quickRepliesEl.appendChild(btn);
    });
  }

  async function sendMessage(text) {
    if (text && text.trim().length > 0) {
      addBubble(text, "user");
    }
    renderQuickReplies([]);
    showTyping();

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text, state: conversationState }),
      });
      const data = await res.json();
      conversationState = data.state;

      hideTyping();
      addBubble(data.reply, "bot", data.urgency);
      renderQuickReplies(data.quick_replies);
    } catch (err) {
      hideTyping();
      addBubble(
        "Sorry, something went wrong reaching the server. Please try again.",
        "bot"
      );
      console.error(err);
    }
  }

  chatForm.addEventListener("submit", (e) => {
    e.preventDefault();
    const text = chatInput.value;
    chatInput.value = "";
    if (text.trim().length === 0) return;
    sendMessage(text);
  });

  resetBtn.addEventListener("click", async () => {
    chatWindow.innerHTML = "";
    renderQuickReplies([]);
    showTyping();
    try {
      const res = await fetch("/api/reset", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      const data = await res.json();
      conversationState = data.state;
      hideTyping();
      addBubble(data.reply, "bot");
    } catch (err) {
      hideTyping();
      console.error(err);
    }
  });

  // Kick off the conversation with an initial greeting from the bot.
  sendMessage("");
})();
