package org.cloudfoundry.samples.music;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.context.junit4.SpringRunner;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;

import static org.hamcrest.Matchers.*;
import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

/**
 * Characterization tests for the Spring Music monolith.
 *
 * PURPOSE: Pin the CURRENT behavior of AlbumController before any modernization work begins.
 * These are NOT correctness tests. They record what the system does today, bugs included.
 *
 * RULE: Do not "fix" a failing test by changing behavior — that is the signal.
 * A failing test means someone changed observable behavior. Investigate before proceeding.
 *
 * Bugs pinned here (must be fixed in the new Album Catalog Service):
 *   - GET /albums/{nonexistentId} returns HTTP 200 with empty body instead of 404
 *   - GET /albums/{deletedId}    returns HTTP 200 with empty body instead of 404
 *
 * Defaults pinned here (must match in new service or be explicitly changed in ADR):
 *   - trackCount serializes as 0 (int primitive, not null) when absent from input
 *   - albumId serializes as null when absent from input
 *   - Server always generates album id — client-supplied id is ignored on PUT
 */
@RunWith(SpringRunner.class)
@SpringBootTest(useMainMethod = SpringBootTest.UseMainMethod.ALWAYS)
@AutoConfigureMockMvc
public class AlbumControllerCharacterizationTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    private String seedAlbumId;

    @Before
    public void resolveOneSeedAlbumId() throws Exception {
        MvcResult result = mockMvc.perform(get("/albums")).andReturn();
        JsonNode albums = objectMapper.readTree(result.getResponse().getContentAsString());
        seedAlbumId = albums.get(0).get("id").asText();
    }

    // =========================================================
    // GET /albums
    // =========================================================

    @Test
    public void getAlbums_returns200() throws Exception {
        mockMvc.perform(get("/albums"))
                .andExpect(status().isOk());
    }

    @Test
    public void getAlbums_returnsApplicationJson() throws Exception {
        mockMvc.perform(get("/albums"))
                .andExpect(content().contentTypeCompatibleWith(MediaType.APPLICATION_JSON));
    }

    @Test
    public void getAlbums_seedDataHas29Albums() throws Exception {
        // albums.json ships 29 albums; AlbumRepositoryPopulator seeds them once (count == 0 guard).
        // This test assumes the DB was clean at startup. If it fails with a count > 29,
        // another test is leaking data — fix that test's cleanup, not this assertion.
        mockMvc.perform(get("/albums"))
                .andExpect(jsonPath("$", hasSize(29)));
    }

    @Test
    public void getAlbums_eachAlbumHasRequiredFields() throws Exception {
        mockMvc.perform(get("/albums"))
                .andExpect(jsonPath("$[*].id",          everyItem(notNullValue())))
                .andExpect(jsonPath("$[*].title",        everyItem(notNullValue())))
                .andExpect(jsonPath("$[*].artist",       everyItem(notNullValue())))
                .andExpect(jsonPath("$[*].releaseYear",  everyItem(notNullValue())))
                .andExpect(jsonPath("$[*].genre",        everyItem(notNullValue())));
    }

    @Test
    public void getAlbums_trackCountIsZeroForAllSeedAlbums() throws Exception {
        // albums.json does not include trackCount.
        // Album.trackCount is a primitive int — it defaults to 0, never null, never absent in JSON.
        // The new service must serialize this as 0 (not null, not omit it) to stay compatible.
        mockMvc.perform(get("/albums"))
                .andExpect(jsonPath("$[*].trackCount", everyItem(is(0))));
    }

    @Test
    public void getAlbums_albumIdIsNullForAllSeedAlbums() throws Exception {
        // albums.json does not include albumId.
        // albumId is a separate String field from id — its purpose is undocumented.
        // It serializes as JSON null (not absent) for seed data.
        // Do NOT assume albumId == id in the new service without investigating this field first.
        mockMvc.perform(get("/albums"))
                .andExpect(jsonPath("$[*].albumId", everyItem(nullValue())));
    }

    @Test
    public void getAlbums_containsKnownSeedEntries() throws Exception {
        mockMvc.perform(get("/albums"))
                .andExpect(jsonPath("$[?(@.title=='Nevermind' && @.artist=='Nirvana')]",             hasSize(1)))
                .andExpect(jsonPath("$[?(@.title=='Thriller' && @.artist=='Michael Jackson')]",       hasSize(1)))
                .andExpect(jsonPath("$[?(@.title=='Abbey Road' && @.artist=='The Beatles')]",         hasSize(1)))
                .andExpect(jsonPath("$[?(@.title=='Texas Flood' && @.artist=='Stevie Ray Vaughan')]", hasSize(1)));
    }

    @Test
    public void getAlbums_genreValuesAreLimitedToKnownSet() throws Exception {
        // Seed data uses only Rock and Blues — no free-text genre in the seed.
        // Pinned so a schema change to enum/validation is visible.
        mockMvc.perform(get("/albums"))
                .andExpect(jsonPath("$[?(@.genre!='Rock' && @.genre!='Blues' && @.genre!='Pop')]", hasSize(0)));
    }

    // =========================================================
    // GET /albums/{id}
    // =========================================================

    @Test
    public void getAlbumById_returns200WithAlbum_whenIdExists() throws Exception {
        mockMvc.perform(get("/albums/" + seedAlbumId))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.id", is(seedAlbumId)));
    }

    @Test
    public void getAlbumById_returns200WithEmptyBody_whenIdNotFound() throws Exception {
        // PINNED BUG: AlbumController.getById() calls repository.findById(id).orElse(null).
        // Spring serializes null as an empty response body with HTTP 200, not 404.
        // The new Album Catalog Service MUST return 404 for missing resources (see ADR-001).
        // If this test starts failing with status 404: the bug was fixed — update this test
        // and remove the note from ADR-001's anti-corruption section.
        MvcResult result = mockMvc.perform(get("/albums/this-id-will-never-exist-xyzzy"))
                .andExpect(status().isOk())
                .andReturn();
        assertEquals(
                "PINNED BUG: missing album must return HTTP 200 + empty body (not 404). " +
                "See AlbumController.getById() — orElse(null) is the root cause.",
                "",
                result.getResponse().getContentAsString()
        );
    }

    // =========================================================
    // PUT /albums  (create)
    // =========================================================

    @Test
    public void putAlbum_returns200WithCreatedAlbum() throws Exception {
        String body = "{\"title\":\"Kind of Blue\",\"artist\":\"Miles Davis\","
                + "\"releaseYear\":\"1959\",\"genre\":\"Jazz\"}";

        MvcResult result = mockMvc.perform(put("/albums")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(body))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.title",       is("Kind of Blue")))
                .andExpect(jsonPath("$.artist",      is("Miles Davis")))
                .andExpect(jsonPath("$.releaseYear", is("1959")))
                .andExpect(jsonPath("$.id",          notNullValue()))
                .andReturn();

        cleanUp(result);
    }

    @Test
    public void putAlbum_serverGeneratesId_ignoringClientSuppliedId() throws Exception {
        // RandomIdGenerator always generates a UUID — any id in the request body is overwritten.
        // Clients must use the id returned in the response, not the one they sent.
        String body = "{\"id\":\"my-own-id\",\"title\":\"Test\",\"artist\":\"Test\","
                + "\"releaseYear\":\"2000\",\"genre\":\"Pop\"}";

        MvcResult result = mockMvc.perform(put("/albums")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(body))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.id", not("my-own-id")))
                .andExpect(jsonPath("$.id", notNullValue()))
                .andReturn();

        cleanUp(result);
    }

    @Test
    public void putAlbum_createdAlbumIsRetrievableByGetById() throws Exception {
        String body = "{\"title\":\"Blue Train\",\"artist\":\"John Coltrane\","
                + "\"releaseYear\":\"1957\",\"genre\":\"Jazz\"}";

        MvcResult result = mockMvc.perform(put("/albums")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(body))
                .andReturn();

        String id = idFrom(result);

        mockMvc.perform(get("/albums/" + id))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.title", is("Blue Train")));

        mockMvc.perform(delete("/albums/" + id));
    }

    @Test
    public void putAlbum_trackCountDefaultsToZero_whenNotSupplied() throws Exception {
        String body = "{\"title\":\"Silence\",\"artist\":\"4\","
                + "\"releaseYear\":\"1952\",\"genre\":\"Experimental\"}";

        MvcResult result = mockMvc.perform(put("/albums")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(body))
                .andExpect(jsonPath("$.trackCount", is(0)))
                .andReturn();

        cleanUp(result);
    }

    // =========================================================
    // POST /albums  (update)
    // =========================================================

    @Test
    public void postAlbum_updatesAlbumAndReturnsNewState() throws Exception {
        // Create a fresh album (don't mutate seed data)
        MvcResult created = mockMvc.perform(put("/albums")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"title\":\"Before\",\"artist\":\"A\",\"releaseYear\":\"2000\",\"genre\":\"Pop\"}"))
                .andReturn();
        String id = idFrom(created);

        String update = "{\"id\":\"" + id + "\",\"title\":\"After\","
                + "\"artist\":\"A\",\"releaseYear\":\"2001\",\"genre\":\"Rock\",\"trackCount\":10}";

        mockMvc.perform(post("/albums")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(update))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.id",          is(id)))
                .andExpect(jsonPath("$.title",        is("After")))
                .andExpect(jsonPath("$.releaseYear",  is("2001")))
                .andExpect(jsonPath("$.trackCount",   is(10)));

        // Verify persistence — change is visible on subsequent GET
        mockMvc.perform(get("/albums/" + id))
                .andExpect(jsonPath("$.title", is("After")));

        mockMvc.perform(delete("/albums/" + id));
    }

    // =========================================================
    // DELETE /albums/{id}
    // =========================================================

    @Test
    public void deleteAlbum_returns200WithEmptyBody() throws Exception {
        MvcResult created = mockMvc.perform(put("/albums")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"title\":\"ToDelete\",\"artist\":\"X\",\"releaseYear\":\"2000\",\"genre\":\"Pop\"}"))
                .andReturn();
        String id = idFrom(created);

        MvcResult deleted = mockMvc.perform(delete("/albums/" + id))
                .andExpect(status().isOk())
                .andReturn();

        assertEquals(
                "DELETE /albums/{id} must return HTTP 200 with empty body (void controller method)",
                "",
                deleted.getResponse().getContentAsString()
        );
    }

    @Test
    public void deleteAlbum_subsequentGetReturns200WithEmptyBody() throws Exception {
        // PINNED BUG: after deletion, GET returns 200 + empty body for the same reason as
        // getAlbumById_returns200WithEmptyBody_whenIdNotFound (orElse(null)).
        MvcResult created = mockMvc.perform(put("/albums")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"title\":\"ToDelete2\",\"artist\":\"X\",\"releaseYear\":\"2000\",\"genre\":\"Pop\"}"))
                .andReturn();
        String id = idFrom(created);

        mockMvc.perform(delete("/albums/" + id)).andExpect(status().isOk());

        MvcResult afterDelete = mockMvc.perform(get("/albums/" + id)).andReturn();
        assertEquals(
                "PINNED BUG: GET after DELETE returns 200 + empty body (not 404). Same root cause as non-existent lookup.",
                "",
                afterDelete.getResponse().getContentAsString()
        );
    }

    // =========================================================
    // GET /appinfo
    // =========================================================

    @Test
    public void appInfo_returns200() throws Exception {
        mockMvc.perform(get("/appinfo"))
                .andExpect(status().isOk());
    }

    @Test
    public void appInfo_responseHasProfilesAndServicesArrays() throws Exception {
        mockMvc.perform(get("/appinfo"))
                .andExpect(jsonPath("$.profiles", notNullValue()))
                .andExpect(jsonPath("$.services",  notNullValue()));
    }

    @Test
    public void appInfo_profilesIsEmptyInDefaultTestContext() throws Exception {
        // No Spring profile active in tests (H2 default, no CF environment)
        mockMvc.perform(get("/appinfo"))
                .andExpect(jsonPath("$.profiles", hasSize(0)));
    }

    @Test
    public void appInfo_servicesIsEmptyWhenNoCfEnvironment() throws Exception {
        // No Cloud Foundry VCAP_SERVICES present in test environment
        mockMvc.perform(get("/appinfo"))
                .andExpect(jsonPath("$.services", hasSize(0)));
    }

    // =========================================================
    // GET /errors/*
    // =========================================================

    @Test
    public void errorsThrow_propagatesNullPointerException() {
        // /errors/throw forces a NullPointerException.
        // Spring Boot 2 MockMvc: exception converted to HTTP 500 response.
        // Spring Boot 3 MockMvc: exception propagates as ServletException wrapping NPE.
        // Either outcome pins the same contract: this endpoint throws an unhandled NPE.
        // NOTE: /errors/kill (System.exit) and /errors/fill-heap (OOM) are NOT tested.
        int status = 0;
        Exception propagated = null;
        try {
            MvcResult result = mockMvc.perform(get("/errors/throw")).andReturn();
            status = result.getResponse().getStatus();
        } catch (Exception e) {
            propagated = e;
        }
        Throwable root = propagated;
        while (root != null && root.getCause() != null) root = root.getCause();
        assertTrue(
                "Expected HTTP 5xx or propagated NullPointerException from /errors/throw",
                (status >= 500) || (root instanceof NullPointerException)
        );
    }

    // =========================================================
    // Helpers
    // =========================================================

    private String idFrom(MvcResult result) throws Exception {
        return objectMapper.readTree(result.getResponse().getContentAsString()).get("id").asText();
    }

    private void cleanUp(MvcResult result) throws Exception {
        mockMvc.perform(delete("/albums/" + idFrom(result)));
    }
}
