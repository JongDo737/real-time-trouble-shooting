<<<<<<< HEAD
FROM node:22-alpine
ENV NODE_ENV=production
WORKDIR /app
COPY --chown=node:node package.json server.mjs ./
COPY --chown=node:node public ./public
USER node
EXPOSE 8080
CMD ["node", "server.mjs"]
=======
FROM nginx:1.27-alpine

COPY . /usr/share/nginx/html

EXPOSE 80
>>>>>>> origin/main
