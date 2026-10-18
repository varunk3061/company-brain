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