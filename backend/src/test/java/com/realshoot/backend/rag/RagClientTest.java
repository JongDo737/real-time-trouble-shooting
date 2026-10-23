package com.realshoot.backend.rag;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.io.IOException;
import java.time.Duration;
import java.util.List;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.reactive.function.client.WebClientResponseException;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.realshoot.backend.auth.Role;
import com.realshoot.backend.rag.RagDtos.RagQueryRequest;
import com.realshoot.backend.rag.RagDtos.TranslateRequest;
import com.realshoot.backend.security.AuthUser;
import com.realshoot.backend.security.JwtProvider;

import okhttp3.mockwebserver.MockResponse;
import okhttp3.mockwebserver.MockWebServer;
import okhttp3.mockwebserver.RecordedRequest;

class RagClientTest {

    private static final AuthUser AGENT = new AuthUser(1L, Role.ADMIN);
    private static final String LLM_TIMEOUT_BODY =
            "{\"error\":{\"code\":\"LLM_TIMEOUT\",\"message\":\"timeout\",\"request_id\":\"r\"}}";

    private MockWebServer server;
    private RagClient client;
    private JwtProvider jwtProvider;

    @BeforeEach
    void setUp() throws IOException {
        server = new MockWebServer();
        server.start();
        jwtProvider = new JwtProvider("test-secret-test-secret-test-secret-32b", 3600);
        client = new RagClient(WebClient.builder(), jwtProvider, new ObjectMapper(),
                server.url("/fastapi").toString(), Duration.ofSeconds(2), Duration.ofSeconds(2));
    }

    @AfterEach
    void tearDown() throws IOException {
        server.shutdown();
    }

    @Test
    void translate는_snake_case로_보내고_JWT를_붙인다() throws InterruptedException {
        server.enqueue(json(200, "{\"translated_text\":\"팬이 돌지 않습니다.\",\"needs_review\":true}"));

        var response = client.translate(translateRequest(), AGENT);

        assertThat(response.translatedText()).isEqualTo("팬이 돌지 않습니다.");
        assertThat(response.needsReview()).isTrue();
        RecordedRequest recorded = server.takeRequest();
        assertThat(recorded.getPath()).isEqualTo("/fastapi/translate");
        assertThat(recorded.getBody().readUtf8()).contains("\"session_id\":\"call-1\"", "\"source_lang\":\"en\"",
                "\"speaker\":\"USER\"");
        String token = recorded.getHeader("Authorization").substring("Bearer ".length());
        assertThat(jwtProvider.parse(token)).isEqualTo(AGENT);
    }

    @Test
    void LLM_TIMEOUT이면_1회_재시도한다() {
        server.enqueue(json(503, LLM_TIMEOUT_BODY));
        server.enqueue(json(200, "{\"translated_text\":\"ok\",\"needs_review\":false}"));

        assertThat(client.translate(translateRequest(), AGENT).translatedText()).isEqualTo("ok");
        assertThat(server.getRequestCount()).isEqualTo(2);
    }

    @Test
    void rag_query_출처의_text를_읽는다() {
        server.enqueue(json(200, """
                {"status":"found","answer":"1. 커넥터 확인","score":0.91,
                 "sources":[{"doc":"CNC-500.pdf","page":87,"section":"조치방법","equipment_name":"CNC-500",
                             "error_code":"E-1042","text":"냉각 팬 커넥터(CN7) 점검","score":0.91}],
                 "needs_review":false,"handoff":false,"attempts":1,"latency_ms":2310}
                """));

        var source = client.ragQuery(new RagQueryRequest("call-1", "q-1", "CNC-500", "E-1042", null), AGENT)
                .sources().get(0);

        assertThat(source.text()).isEqualTo("냉각 팬 커넥터(CN7) 점검");
        assertThat(source.section()).isEqualTo("조치방법");
    }

    @Test
    void 재시도도_실패하면_예외() {
        server.enqueue(json(503, LLM_TIMEOUT_BODY));
        server.enqueue(json(503, LLM_TIMEOUT_BODY));

        assertThatThrownBy(() -> client.translate(translateRequest(), AGENT))
                .isInstanceOf(WebClientResponseException.class);
        assertThat(server.getRequestCount()).isEqualTo(2);
    }

    @Test
    void 다른_오류는_재시도하지_않는다() {
        server.enqueue(json(503, "{\"error\":{\"code\":\"LLM_UNAVAILABLE\"}}"));

        assertThatThrownBy(() -> client.translate(translateRequest(), AGENT))
                .isInstanceOf(WebClientResponseException.class);
        assertThat(server.getRequestCount()).isEqualTo(1);
    }

    @Test
    void rag_query의_not_found는_정상_응답() {
        server.enqueue(json(200,
                "{\"status\":\"not_found\",\"answer\":null,\"sources\":[],\"needs_review\":false,\"handoff\":true}"));

        var response = client.ragQuery(new RagQueryRequest("call-1", "q-1", "CNC-500", "E-1042", null), AGENT);

        assertThat(response.status()).isEqualTo("not_found");
        assertThat(response.handoff()).isTrue();
        assertThat(SolutionResponse.from(response).status()).isEqualTo("not_found");
    }

    private static TranslateRequest translateRequest() {
        return new TranslateRequest("call-1", "u-1", "The fan is not spinning.", "en", "ko", "USER", "CNC-500",
                "E-1042", List.of());
    }

    private static MockResponse json(int status, String body) {
        return new MockResponse().setResponseCode(status).setHeader("Content-Type", "application/json").setBody(body);
    }
}
