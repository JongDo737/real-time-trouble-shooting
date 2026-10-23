FROM gradle:8.11-jdk21 AS build
WORKDIR /app
COPY . .
RUN gradle bootJar -x test --no-daemon \
 && find build/libs -name "*.jar" ! -name "*-plain.jar" -exec cp {} /app/app.jar \;

FROM eclipse-temurin:21-jre
WORKDIR /app
COPY --from=build /app/app.jar app.jar
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "app.jar"]
