import BASE_URL from "@/lib/api";

export async function loginUser(role, credentials) {
    const endpoint = 
        role === "admin" ? "/login" : "/employee/login";
    
    const response = await fetch(`${BASE_URL}${endpoint}` , {
        method : "POST",
        headers : {
            "Content-Type" : "application/json",
        },
        body: JSON.stringify({
            email: credentials.email,
            password: credentials.password,
        }),
    });

    // FastAPI commonly return errors in the 'detail' field
    const data = await response.json().catch(()=>({}));

    if (!response.ok) {
        throw new Error(
            typeof data.detail === "string"
                ?   data.detail 
                : typeof data.message === "string"
                    ? data.message
                    : `Login Failed (${response.status}).`
        );
    }

    return data;
}

export async function getAdminProfile() {
    const token =
        localStorage.getItem("access_token") ||
        sessionStorage.getItem("access_token");

    if (!token) {
        throw new Error("NOT_AUTHENTICATED");
    }

    const response = await fetch(`${BASE_URL}/admin/me`, {
        method: "GET",
        headers: { Authorization: `Bearer ${token}` },
    });

    const data = await response.json().catch(() => ({}));

    if (response.status === 401 || response.status === 403) {
        throw new Error("NOT_AUTHENTICATED");
    }
    if (!response.ok) {
        throw new Error(data.detail || `Unable to load profile (${response.status}).`);
    }

    return data;
}
