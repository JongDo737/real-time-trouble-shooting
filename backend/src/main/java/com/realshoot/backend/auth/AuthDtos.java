package com.realshoot.backend.auth;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

public final class AuthDtos {

    private AuthDtos() {
    }

    /** A-1. 고객사 계정만 가입 (role은 받지 않음) */
    public record SignupRequest(
            @NotBlank @Pattern(regexp = "^[A-Za-z0-9_]{4,50}$", message = "4~50자, 영문 · 숫자 · _만 사용할 수 있습니다.")
            String username,
            @NotBlank @Size(min = 8, max = 64) String password,
            @NotBlank @Size(max = 20) String clientName,
            @NotBlank @Size(max = 50) String companyName,
            @NotBlank @Size(max = 30) String position) {

        @Override
        public String toString() {
            return "SignupRequest[username=" + username + "]";
        }
    }

    /** A-2 */
    public record LoginRequest(@NotBlank String username, @NotBlank String password) {

        @Override
        public String toString() {
            return "LoginRequest[username=" + username + "]";
        }
    }

    public record LoginResponse(String accessToken, String tokenType, long expiresIn, UserInfo user) {
    }

    public record UserInfo(Long id, String username, Role role, String clientName, String companyName,
                           String position) {

        public static UserInfo from(User user) {
            return new UserInfo(user.getId(), user.getUsername(), user.getRole(), user.getClientName(),
                    user.getCompanyName(), user.getPosition());
        }
    }
}
