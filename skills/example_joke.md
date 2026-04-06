---
name: joke
description: Tell a programming joke. This is a prompt-only skill (no endpoint).
parameters:
  topic:
    type: string
    description: "Topic for the joke (e.g. 'python', 'javascript', 'devops')"
    required: false
---

When the user asks for a joke, generate a short, clean programming joke.
If a topic is provided, make the joke about that topic.
Keep it to 1-3 sentences. Avoid offensive content.
