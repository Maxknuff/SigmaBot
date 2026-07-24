module.exports = {
  apps: [
    {
      name: 'sigmabot',
      script: 'bot.py',
      interpreter: 'python',
      env: {
        NODE_ENV: 'production'
      },
      error_file: './logs/error.log',
      out_file: './logs/out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
      instances: 1,
      max_memory_restart: '512M',
      watch: false,
      ignore_watch: ['node_modules', '.git', 'data', 'logs'],
      restart_delay: 5000,
      autorestart: true
    }
  ]
};
