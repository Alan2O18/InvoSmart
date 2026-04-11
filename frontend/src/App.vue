<script setup>
</script>

<template>
  <header>
    <nav>
      <router-link to="/">Home</router-link>
      <router-link to="/stamps">Stamps</router-link>
      <router-link to="/settings">Settings</router-link>
    </nav>
  </header>

  <main>
    <router-view />
  </main>
</template>

<style scoped>
header {
  line-height: 1.5;
  padding: 1rem;
  background-color: #1a1a1a;
  border-bottom: 1px solid #333;
}

nav {
  display: flex;
  gap: 1rem;
}

nav a {
  color: #fff;
  text-decoration: none;
}

nav a:hover {
  color: #42b883;
}

main {
  flex: 1;
  display: flex;
  flex-direction: column;
}
</style>
