# Performance Rules

## General

- Optimize hot paths identified by profiling
- Use caching for frequently accessed data
- Avoid N+1 query problems
- Use appropriate data structures and algorithms

## Database

- Index frequently queried columns
- Use connection pooling
- Batch operations when possible
- Avoid SELECT *, fetch only what you need

## Network

- Minimize round trips
- Use compression
- Implement proper timeouts
- Consider CDNs for static assets

## Code

- Avoid premature optimization
- Profile before optimizing
- Keep critical paths simple and focused
- Use lazy loading where appropriate
