-- Application tables belong in a schema excluded from Supabase's Data API.
CREATE TABLE tracker.problems (
    user_id UUID NOT NULL,
    number INTEGER NOT NULL CHECK (number > 0),
    name TEXT NOT NULL,
    difficulty TEXT NOT NULL,
    topic TEXT NOT NULL,
    notes TEXT NOT NULL,
    archived BOOLEAN NOT NULL DEFAULT FALSE,
    review_due_on DATE,
    historical_attempts INTEGER NOT NULL DEFAULT 0 CHECK (historical_attempts >= 0),
    PRIMARY KEY (user_id, number)
);

CREATE TABLE tracker.reviews (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id UUID NOT NULL,
    problem_number INTEGER NOT NULL,
    reviewed_on DATE NOT NULL,
    mastery_level TEXT NOT NULL,
    FOREIGN KEY (user_id, problem_number)
        REFERENCES tracker.problems (user_id, number) ON DELETE CASCADE
);
CREATE INDEX reviews_owner_problem_date
    ON tracker.reviews (user_id, problem_number, reviewed_on, id);

CREATE TABLE tracker.problem_statements (
    user_id UUID NOT NULL,
    problem_number INTEGER NOT NULL,
    html TEXT NOT NULL,
    title_slug TEXT,
    PRIMARY KEY (user_id, problem_number),
    FOREIGN KEY (user_id, problem_number)
        REFERENCES tracker.problems (user_id, number) ON DELETE CASCADE
);

REVOKE ALL ON ALL TABLES IN SCHEMA tracker FROM PUBLIC;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA tracker FROM PUBLIC;
