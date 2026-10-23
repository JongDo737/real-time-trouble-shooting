package com.realshoot.backend.security;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import org.junit.jupiter.api.Test;

import com.realshoot.backend.auth.Role;
import com.realshoot.backend.global.error.ApiException;
import com.realshoot.backend.global.error.ErrorCode;

class JwtProviderTest {

    private static final String SECRET = "test-secret-test-secret-test-secret-32b";

    private final JwtProvider provider = new JwtProvider(SECRET, 3600);

    @Test
    void 발급한_토큰에서_사용자와_역할을_꺼낸다() {
        String token = provider.issue(17L, Role.ADMIN);

        AuthUser user = provider.parseBearer("Bearer " + token);

        assertThat(user).isEqualTo(new AuthUser(17L, Role.ADMIN));
    }

    @Test
    void 다른_키로_서명한_토큰은_401() {
        String token = new JwtProvider("another-secret-another-secret-another-32", 3600).issue(1L, Role.USER);

        assertUnauthorized(() -> provider.parse(token));
    }

    @Test
    void 만료된_토큰은_401() {
        String token = new JwtProvider(SECRET, -10).issue(1L, Role.USER);

        assertUnauthorized(() -> provider.parse(token));
    }

    @Test
    void Bearer_형식이_아니면_401() {
        assertUnauthorized(() -> provider.parseBearer(null));
        assertUnauthorized(() -> provider.parseBearer("Token abc"));
        assertUnauthorized(() -> provider.parseBearer("Bearer not-a-jwt"));
    }

    private void assertUnauthorized(Runnable action) {
        assertThatThrownBy(action::run)
                .isInstanceOf(ApiException.class)
                .extracting(e -> ((ApiException) e).getErrorCode())
                .isEqualTo(ErrorCode.UNAUTHORIZED);
    }
}
