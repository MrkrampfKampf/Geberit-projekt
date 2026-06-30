const requiredVariables = [
    "SUPABASE_URL",
    "SUPABASE_PUBLISHABLE_KEY",
    "SUPABASE_SECRET_KEY",
    "SUPABASE_JWKS_URL"
];

const missingVariables = requiredVariables.filter(name => !process.env[name]);

if (missingVariables.length > 0) {
    console.error(`Missing environment variables: ${missingVariables.join(", ")}`);
    process.exit(1);
}

console.log("Supabase environment variables are configured.");
