import pino from 'pino';

const logger = pino({
  level: process.env.LOG_LEVEL ?? 'info',
  base: {
    service: 'coinmaster',
    env: process.env.NODE_ENV ?? 'development',
  },
});

export default logger;
