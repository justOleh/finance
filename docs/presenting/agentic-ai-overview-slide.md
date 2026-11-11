# Slide: Agentic AI on AWS, and why this design

**Purpose** One slide that sets up the talk: what agentic AI on AWS can do, the ways to integrate an agent with an existing app, the AWS services offered, and why this project uses the design it does.
**Status** Draft content. Facts about AWS services come from ADR-014 and the sources it cites. Re-check service names and features against the AWS docs before the talk.

## Slide title

**Agentic AI on AWS: what is possible and why we chose this design**

## Left column: what is possible

- An agent is a model that calls tools in a loop until it reaches an answer.
- Typical uses: answer questions over your own data, take actions through APIs, and draft changes for a human to approve.
- Agents need four things beyond the model: tools, identity (whose data), guardrails and limits, and observability.

## Middle column: ways to integrate an agent with an existing app

| Option | Trade-off |
|---|---|
| Agent inside the app backend (a `/chat` route) | Simple, but the talk has little to show and the agent is not a separate facade |
| Lambda or container with a hand-built tool loop | Full control; you build streaming, auth and sessions yourself |
| Managed agent runtime (AgentCore Runtime) with a framework (Strands) | Managed sessions, streaming and JWT auth at the edge; a new service to learn |
| Agent reads or writes the database directly | Duplicates business rules and tenant isolation; rejected |
| Separate chat app with its own tools | Second login and hosting; the two interfaces stop sitting side by side |
| Agent exposed as MCP tools | Good for reuse; adds a service and token forwarding before there is a working chat |

## Right column: what AWS offers

- **Amazon Bedrock AgentCore**: the managed layer. Runtime (hosts the agent, validates the Cognito token), Gateway, Identity, Memory, Observability.
- **Strands Agents SDK**: the open-source framework used in the agent code.
- **Amazon Bedrock**: model access. Here, Amazon Nova Pro in the EU region.
- **Bedrock Agents**: the older managed service. Less control over tools and streaming; not chosen.

## Bottom band: why this implementation

1. **One source of truth.** The agent calls the existing REST API with the user's own token. Business rules and tenant isolation stay in one place (ADR-009, ADR-014).
2. **Safe by design.** The agent has read and draft tools only. The user clicks Save, so the model never writes data (human approval).
3. **Least privilege.** The runtime's IAM role can invoke one model and nothing else. The user's token decides which data is touched.
4. **Managed where it matters.** AgentCore handles streaming, sessions and token checks, so the time goes into the agent and its evals.
5. **Comparable.** The same tasks run through the chat and the normal UI, so the talk can compare time, cost and errors.

## Speaker note

Start with the bottom band if time is short: it's the decision the talk defends. The middle column is where the audience is most likely to ask "why not X?", so the rejected options in ADR-014 are the backup.

## Sources

- [ADR-014: Chat agent as a facade over the existing API](../architecture/ADRs/ADR-014-chat-agent-facade-on-agentcore.md)
- [Implementation plan 04](../implementation/04-chat-agent-facade.md)
- [Propagate user authorization context in AI agents with Amazon Bedrock AgentCore](https://aws.amazon.com/blogs/security/propagate-user-authorization-context-in-ai-agents-with-amazon-bedrock-agentcore/)
