import { withSupabase } from "@supabase/server";

export default {
    fetch: withSupabase({ auth: "publishable" }, async (_req, ctx) => {
        const { data, error } = await ctx.supabase
            .from("products")
            .select("*")
            .eq("active", true)
            .order("sort_order", { ascending: true });

        if (error) {
            return Response.json({ error: error.message }, { status: 500 });
        }

        return Response.json(data);
    })
};
