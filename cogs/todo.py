from discord.ext import commands
from cogs.utils import bounded_text, send_chunks


class Todo(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command()
    async def todo_add(self, ctx, *, text: str):
        bounded_text(text, 1000)
        await self.bot.db.execute(
            "INSERT INTO todos (guild_id, channel_id, author_id, content, done) VALUES (?, ?, ?, ?, ?)",
            (ctx.guild.id, ctx.channel.id, ctx.author.id, text, 0),
        )
        await self.bot.db.commit()
        await ctx.send("Aufgabe hinzugefügt.")

    @commands.command()
    async def todo_list(self, ctx):
        cur = await self.bot.db.execute(
            "SELECT id, content, done FROM todos WHERE guild_id = ? AND channel_id = ?", (ctx.guild.id, ctx.channel.id)
        )
        rows = await cur.fetchall()
        if not rows:
            await ctx.send("Keine Aufgaben.")
            return
        out_lines = []
        for r in rows:
            id_, content, done = r
            status = "x" if done else " "
            out_lines.append(f"{id_}. [{status}] {content}")
        await send_chunks(ctx, "\n".join(out_lines))

    @commands.command()
    async def todo_done(self, ctx, id: int):
        cur = await self.bot.db.execute(
            "UPDATE todos SET done = 1 WHERE id = ? AND guild_id = ? AND channel_id = ?",
            (id, ctx.guild.id, ctx.channel.id),
        )
        await self.bot.db.commit()
        await ctx.send(
            "Aufgabe als erledigt markiert." if cur.rowcount else "Aufgabe in diesem Channel nicht gefunden."
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Todo(bot))
