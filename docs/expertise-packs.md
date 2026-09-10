[English](expertise-packs.md) | [Türkçe](expertise-packs.tr.md)

# Opt-in expertise packs

v0.3.0 includes two optional skill packs. They add a focused checklist to the base bounded workflow when the user explicitly selects one or asks for that expertise.

## UI design

Invoke `$bounded-orchestrator-ui-design` together with `$bounded-orchestrator` for work where UI or UX design expertise is part of the requested outcome.

The pack asks the owner to define the audience, key action, states, constraints, and existing design-system elements. It covers interaction states, supported layouts, keyboard use, focus, labels, contrast, reduced motion, zoom, and realistic content. It asks for an intentional product-specific direction and discourages unsupported claims about research, accessibility, or compatibility.

## Security review

Invoke `$bounded-orchestrator-security-review` together with `$bounded-orchestrator` when the user requests a security-focused analysis or review.

The pack asks for relevant assets, trust boundaries, entry points, actors, data sensitivity, and abuse cases. It routes attention to authentication, authorization, validation, secrets, personal data, logs, unsafe execution boundaries, dependencies, replay, rate limits, and denial-of-service exposure when those areas apply. Findings must state evidence and confidence without inflating severity.

## Boundary

Both packs are instructions. They do not add tools, create agents, change models or sandboxes, grant credentials, authorize external tests, or enforce behavior. The base rules remain in force: one accountable owner, one writer per scope, no recursive delegation, independent verification, frozen-candidate review, finite repair loops, and explicit authority for external effects.
