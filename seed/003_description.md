# AI Chat Agent Service

## What We Are Building

We need a backend service in Java 21, Spring Boot 3 (WebFlux), and Spring AI that powers an interactive chat assistant. Users send messages in a conversation, the agent thinks through the request, calls backend tools when it needs real data or actions, and streams its answer back word by word in real time so the UI feels fast and responsive.

## How It Should Work

### Core Experience

Instead of making the user wait 10 seconds staring at a loading spinner, the chat endpoint should stream responses back over Server-Sent Events (SSE) as tokens arrive from the AI model. When the agent needs to look something up or run an action (via Spring AI tools), it should run that step automatically, let the user know what it's doing, and continue answering.

### Key Rules to Respect

- **Keep Users Separated:** Every chat session belongs to a specific user and tenant. Nobody should ever be able to read or send messages into someone else's conversation (return `403 Forbidden` if they try).
- **Don't Let the Agent Loop Forever:** When the AI calls tools to solve a problem, cap it at **5 tool calls** per message and a **30-second timeout**. If it hits either limit, stop cleanly and tell the user rather than hanging the request.
- **Manage Conversation Memory:** Keep the last **12 messages** in full detail so the assistant remembers the immediate flow of the chat, and summarize older messages into a running summary so the conversation never crashes the model's **16,000-token** context limit.
- **Keep It Non-Blocking:** Since this runs on Spring WebFlux, streaming responses and waiting on LLM APIs must not block Netty event-loop threads.
- **Save the Chat History:** Store every user message, tool call, and assistant reply as an append-only history log (along with token counts) so users can reload past chats and we can track usage.

## Main Terms

- **Chat Session:** A continuous conversation thread owned by one user.
- **Turn:** One round-trip where the user sends a message and the agent replies.
- **Tool Call:** A backend function the AI invokes during a turn to fetch data or perform an action.
- **Context Window:** The recent messages plus a rolling summary sent to the model on each turn.
- **Token Stream:** The live SSE feed sending text chunks and status updates back to the client.