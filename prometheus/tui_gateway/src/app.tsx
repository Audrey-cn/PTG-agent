import { render, Box, Text } from 'ink';
import React from 'react';

/**
 * Prometheus TUI - React Component
 *
 * A modern terminal UI built with Ink (React for CLI).
 * Provides:
 * - Fixed input area at top (no jumping)
 * - Streaming output in real-time
 * - Sub-agent tree visualization
 * - Copy-to-clipboard support
 */

function App() {
  return (
    <Box flexDirection="column" height={100}>
      <Box>
        <Text bold>Prometheus TUI</Text>
      </Box>
      <Box flexDirection="column" flexGrow={1}>
        <Text>Welcome to Prometheus!</Text>
        <Text dimColor>Type your message below...</Text>
      </Box>
    </Box>
  );
}

render(<App />);
