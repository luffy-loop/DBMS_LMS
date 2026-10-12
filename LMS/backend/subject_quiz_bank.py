"""Immediate subject-specific MCQ banks used by Quiz Lab when no live AI worker is available."""

# Each entry is (question, correct answer, distractor 1, distractor 2, distractor 3, explanation).
BANKS = {
"dbms": [
("What is the main purpose of a primary key?","Uniquely identify each row","Store duplicate rows","Encrypt every column","Sort every query automatically","A primary key uniquely identifies a row."),
("What does a foreign key enforce?","Referential integrity","Image compression","CPU scheduling","Column encryption","A foreign key references a key in another table."),
("Which normal form requires atomic column values?","First Normal Form (1NF)","Fourth Normal Form (4NF)","Third Normal Form (3NF)","Boyce-Codd Normal Form only","1NF requires atomic values and removes repeating groups."),
("What does normalization primarily reduce?","Redundant data and update anomalies","Network latency","CPU instruction count","Password entropy","Normalization organizes data to reduce redundancy and anomalies."),
("Which ACID property makes a transaction all-or-nothing?","Atomicity","Isolation","Durability","Consistency","Atomicity prevents partial transaction commits."),
("Which SQL clause filters rows before grouping?","WHERE","HAVING","ORDER BY","GROUP BY","WHERE filters individual rows before aggregation."),
("Which SQL clause filters aggregated groups?","HAVING","FROM","INSERT","VALUES","HAVING filters groups after aggregation."),
("What does an INNER JOIN return?","Rows with matching join values in both inputs","Every possible row pair","Only unmatched rows","Only column names","An inner join returns rows satisfying the join condition."),
("What is the purpose of a database index?","Speed up suitable data lookups","Guarantee every query is faster","Replace all table data","Prevent every deadlock","Indexes can accelerate reads with storage and write overhead."),
("Which SQL command retrieves data?","SELECT","UPDATE","DROP","GRANT","SELECT queries data from one or more tables."),
("What does COMMIT do?","Save transaction changes","Undo the current transaction","Create a database user","Remove an index","COMMIT makes transaction changes durable."),
("What does ROLLBACK do before commit?","Undo uncommitted transaction changes","Create a backup","Sort a result set","Grant table permissions","ROLLBACK cancels uncommitted changes."),
("What does GROUP BY commonly support?","Aggregate results for each group","Encrypt a table","Rename a database server","Force table deletion","GROUP BY supports COUNT, SUM, and other aggregates."),
("What is a database transaction?","A logical unit of database work","A physical network cable","A UI component","A compiler","A transaction groups database operations into one logical unit."),
("What is a common characteristic of NoSQL databases?","Flexible data models for access patterns","They only store spreadsheets","They require every query to use SQL joins","They cannot be distributed","NoSQL systems support several non-relational data models."),
],
"os": [
("What is a process?","A program in execution with managed resources","A database table","A network protocol","A source-code comment","A process is an executing program with its own context and resources."),
("What is a thread within a process?","An execution path sharing process resources","A separate physical CPU","A file-system partition","A database index","Threads share process resources while maintaining their own execution state."),
("What is a context switch?","Saving one execution state and restoring another","Deleting the kernel","Formatting a disk","Compiling a query","The OS switches CPU execution by saving and restoring state."),
("Which condition describes deadlock?","Processes wait indefinitely for resources held by one another","Every process finishes immediately","The CPU has no instructions","A file is read sequentially","Deadlock can arise when resource waits form a cycle."),
("What does a mutex protect?","A critical section accessed by shared threads","A database schema from syntax errors","A display's brightness","A network address from routing","A mutex provides mutual exclusion around shared state."),
("What is a semaphore commonly used for?","Coordinate access to shared resources","Translate source code","Store permanent files only","Replace virtual memory","Semaphore counters coordinate access and signal waiting work."),
("What is virtual memory?","An abstraction providing processes a logical address space","A physical RAM chip","A CPU register only","A type of database join","Virtual memory maps virtual addresses to physical memory and may use disk pages."),
("What is paging?","Dividing memory into fixed-size pages and frames","Sorting files by name","Scheduling network packets only","Encrypting source code","Paging maps fixed-size virtual pages to physical frames."),
("What does a CPU scheduler decide?","Which ready task should run next","Which columns are primary keys","How a web page is styled","Which file format is compressed","The scheduler selects work from runnable tasks."),
("What is a system call?","A controlled request for an operating-system service","A function that only changes CSS","A SQL table constraint","A hardware battery","System calls let programs request services from the kernel."),
("What is an interrupt?","A signal that requests CPU attention","A duplicate database row","A type of source-code loop","A permanent file deletion","Interrupts notify the processor of events requiring attention."),
("What is a race condition?","A result depends on timing of concurrent operations","A process always runs first","A disk has no free sectors","A query has a syntax error","Unsynchronized shared-state access can make results timing-dependent."),
("What is starvation in scheduling?","A task waits indefinitely because others keep getting resources","All tasks complete together","A page is loaded from disk","A process owns every resource","Starvation occurs when a task is repeatedly denied needed resources."),
("What is thrashing?","Excessive paging that leaves little time for useful work","A fast context switch","A database commit","A thread finishing normally","Thrashing occurs when memory pressure causes excessive page faults."),
("What is the kernel?","The core OS component managing hardware and resources","A user document","A relational join","A browser extension","The kernel provides core process, memory, device, and system-call services."),
],
"dsa": [
("Which data structure follows last-in, first-out order?","Stack","Queue","Graph","Hash table","A stack removes the most recently added item first."),
("Which data structure follows first-in, first-out order?","Queue","Stack","Heap","Binary search tree","A queue removes the earliest added item first."),
("What is binary search's time complexity on sorted data?","O(log n)","O(n^2)","O(1) for every input","O(2^n)","Binary search halves the remaining interval at each step."),
("What condition does binary search require?","The searched sequence is ordered","Every item is a graph","All values are identical","Data must be stored on a stack","Binary search relies on ordering to discard half the interval."),
("What is merge sort's average time complexity?","O(n log n)","O(n^2)","O(log log n)","O(2^n)","Merge sort divides input and merges sorted halves."),
("What does a linked-list node typically contain?","A value and one or more links","Only a database password","A fixed-size matrix only","A CPU instruction register","Nodes store data and references to other nodes."),
("What does a hash table provide on average?","Fast key-based lookup","Guaranteed sorted traversal","Automatic shortest paths","A recursive call stack","A good hash function supports average constant-time lookup."),
("What property defines a binary search tree?","Left keys are smaller and right keys larger under its ordering rule","Every node has exactly four children","Every path has equal length","All nodes are stored in a queue","A BST maintains ordering across its subtrees."),
("Which structure is commonly used by breadth-first search?","Queue","Stack only","Hash function only","Priority-free file","BFS explores nearby vertices first using a queue."),
("Which structure naturally supports depth-first traversal?","Stack","FIFO queue only","SQL index","Circular buffer only","DFS uses an explicit stack or recursion."),
("What is a heap commonly used to implement?","A priority queue","A relational foreign key","A text editor","A network firewall rule","A heap efficiently retrieves the highest- or lowest-priority item."),
("What does Big-O notation describe?","How resource use grows with input size","Exact runtime on every computer","The number of source files","A programming language version","Big-O expresses asymptotic growth."),
("What is recursion's base case for?","Stop recursive calls and return a result","Increase recursion depth forever","Sort every array automatically","Allocate every possible object","A base case prevents unbounded recursion."),
("What is dynamic programming useful for?","Reuse solutions to overlapping subproblems","Avoid storing all intermediate results","Only process network packets","Guarantee constant-time algorithms","Dynamic programming stores or reuses subproblem results."),
("What does a graph adjacency list represent?","Each vertex's neighboring vertices","Only an array's sorted order","A stack's top value","A database transaction log","An adjacency list records neighbors for each vertex."),
],
"ml": [
("What characterizes supervised learning?","Training examples include target labels","There are no training examples","Only database indexes are used","The model never receives feedback","Supervised models learn from examples paired with targets."),
("What characterizes unsupervised learning?","Find patterns without provided target labels","Every example has a known class","It only compiles source code","It always requires human-written rules","Unsupervised methods discover structure in unlabeled data."),
("Which task predicts a category such as spam or not spam?","Classification","Regression","Sorting","Compression","Classification predicts discrete classes."),
("Which task predicts a continuous numeric value?","Regression","Clustering","Classification only","Tokenization","Regression estimates numeric outcomes."),
("What is overfitting?","Learning training details that do not generalize well","Failing to load the dataset","Using no model parameters","Always getting every prediction correct","Overfit models perform well on training data but poorly on unseen data."),
("What is regularization used for?","Discourage overly complex models","Increase label leakage","Remove the test set","Guarantee zero prediction error","Regularization penalizes complexity to improve generalization."),
("Why keep a test set separate?","Estimate performance on unseen data","Train repeatedly on test labels","Store source code","Replace feature engineering","A held-out test set estimates generalization."),
("What does cross-validation help estimate?","Model performance across data splits","CPU clock speed","Database normalization level","A sensor's voltage","Cross-validation evaluates multiple train/validation splits."),
("What is feature scaling?","Transform numeric features to comparable scales","Delete all target labels","Encrypt model weights","Turn a classifier into a database","Scaling helps optimization and distance-based algorithms."),
("What does a confusion matrix summarize?","Counts of predicted versus actual classes","Memory addresses","Database relationships","CPU process states","A confusion matrix records true and false predictions by class."),
("What does precision measure?","Fraction of positive predictions that are correct","Fraction of negatives found","Training-set size","Number of model layers","Precision is true positives divided by predicted positives."),
("What does recall measure?","Fraction of actual positives that are found","Fraction of positive predictions that are correct","Number of features","Size of a loss function","Recall is true positives divided by actual positives."),
("What does gradient descent do?","Update parameters to reduce a loss function","Sort training rows alphabetically","Create labels automatically","Guarantee a global optimum for every model","Gradient descent moves parameters opposite the loss gradient."),
("What is a decision tree?","A model that predicts through feature-based splits","A relational database engine","A network cable","A queue implementation only","Decision trees recursively split examples using feature conditions."),
("What does clustering aim to do?","Group similar examples without predefined labels","Predict only continuous targets","Encrypt every feature","Replace training data with code","Clustering groups examples based on similarity."),
],
"iot": [
("What is a microcontroller?","A compact computer on a chip for embedded control","A database server rack","A cloud-only spreadsheet","A type of SQL join","Microcontrollers integrate a processor, memory, and peripherals."),
("What does a sensor do in an IoT device?","Measure a physical condition","Move a mechanical load directly","Compile firmware","Route every internet packet","Sensors convert physical phenomena into measurable signals."),
("What does an actuator do?","Cause a physical action from a control signal","Only store database rows","Measure temperature without interaction","Encrypt source code","Actuators drive outputs such as motors, valves, or relays."),
("What is firmware?","Software stored to control an embedded device","A cloud database schema","A type of sensor","A network topology diagram","Firmware implements device-specific behavior."),
("What is MQTT commonly used for?","Lightweight publish-subscribe messaging for IoT","Relational table normalization","CPU cache replacement","Image rendering","MQTT is a lightweight messaging protocol for constrained devices."),
("What is edge computing?","Process data near where it is produced","Send every operation to a distant cloud first","Store all data only on paper","Replace sensors with databases","Edge processing can reduce latency and bandwidth use."),
("What is a real-time system designed to meet?","Timing deadlines as well as functional requirements","Only maximize screen resolution","Always use the most memory","Avoid all interrupts","Real-time correctness includes completing work within deadlines."),
("What does an ADC do?","Convert an analog signal into a digital value","Convert source code into machine code","Route messages over Wi-Fi","Control a SQL transaction","An ADC samples analog signals into digital representations."),
("What is PWM commonly used to control?","Average power delivered to a load using duty cycle","Database keys","Network name resolution","File permissions only","Pulse-width modulation adjusts a digital output's duty cycle."),
("Which bus commonly uses two-wire synchronous communication?","I2C","UART","HDMI only","Ethernet fiber only","I2C uses serial data and serial clock lines."),
("Which interface commonly uses clock, input, output, and chip-select lines?","SPI","UART","DNS","HTTP","SPI is a synchronous serial interface."),
("What is a common feature of UART communication?","Asynchronous serial data with configured baud rate","A mandatory shared clock line","A relational query plan","An analog-only signal","UART typically transmits asynchronous serial frames without a shared clock."),
("Why are low-power modes important for IoT?","Extend battery life","Increase unnecessary radio traffic","Disable all security","Guarantee unlimited storage","Sleep modes reduce energy use between tasks."),
("What does an IoT gateway often do?","Bridge local devices to other networks or cloud services","Replace every sensor","Act only as a display","Normalize database tables","Gateways aggregate or translate traffic between network domains."),
("Why use secure boot on an embedded device?","Verify trusted firmware before execution","Increase sensor noise","Disable authentication","Make updates impossible by design","Secure boot checks firmware integrity and authenticity at startup."),
],
"distributed": [
("What is replication in a distributed system?","Maintain copies of data on multiple nodes","Sort one local array","Remove all network communication","Compile a single source file","Replication can improve availability and read scalability."),
("What is sharding?","Split data across nodes using a partitioning rule","Copy all data to every node","Encrypt a single password","Merge every table into one","Sharding distributes different data partitions across nodes."),
("What does a load balancer do?","Distribute incoming requests across available targets","Compile backend source code","Normalize a database","Store only user passwords","Load balancers route requests among service instances."),
("What is a message queue useful for?","Decouple producers from consumers asynchronously","Guarantee all requests run in one process","Replace all storage","Prevent every possible failure","Queues buffer work and reduce direct timing dependencies."),
("What is the goal of a consensus protocol?","Help nodes agree on a value or decision","Make all nodes physically identical","Remove the need for networking","Compress every response","Consensus coordinates agreement despite some node or network failures."),
("What does eventual consistency mean?","Replicas converge if updates stop and communication recovers","Every read is always linearizable","No replica ever changes","Every write is rejected","Eventual consistency permits temporary divergence before convergence."),
("What does the CAP trade-off concern?","Consistency, availability, and partition tolerance during a partition","CPU, memory, and disk size","Classes, attributes, and procedures","Caching, authentication, and passwords","CAP describes limits on consistency and availability when partitions occur."),
("What is a REST API commonly organized around?","Resources accessed through HTTP methods","CPU registers","Physical sensor voltage","Only binary files","REST-style APIs expose resources and use HTTP semantics."),
("What does idempotency mean for an operation?","Repeating it has the same intended effect as doing it once","Every request creates a new record","It always runs faster","It cannot fail","Idempotency makes safe retries possible."),
("Why use exponential backoff for retries?","Increase delays between repeated attempts","Retry continuously with no pause","Delete the service after one error","Disable all timeouts","Backoff reduces retry storms during transient failures."),
("What is a circuit breaker pattern for?","Temporarily stop calls to a failing dependency","Encrypt all API payloads","Guarantee zero latency","Replace a database schema","Circuit breakers prevent repeated calls from amplifying failures."),
("What is a microservice?","A relatively independently deployable service around a capability","A single SQL column","A hardware interrupt","A CSS selector","Microservices split an application into independently deployable capabilities."),
("What is caching intended to improve?","Reuse recent or expensive results to reduce latency or work","Make every result permanently fresh","Replace authorization checks","Guarantee no memory use","Caches trade memory and invalidation complexity for faster access."),
("What is observability commonly built from?","Logs, metrics, and traces","Only source-code comments","Only CSS and HTML","Only a database password","These signals help operators understand system behavior."),
("Why should distributed operations have timeouts?","Bound how long callers wait for unresponsive dependencies","Guarantee the dependency succeeds","Remove the need for monitoring","Make network latency zero","Timeouts limit resource occupation when dependencies stall."),
],
"general": [
("What is an algorithm?","A finite procedure for solving a problem","A physical network connector","A database user account","A display resolution","Algorithms describe step-by-step computational procedures."),
("What is an API?","A defined interface for software components to communicate","A computer battery","A storage partition only","A type of monitor","APIs define operations and data exchanged between components."),
("What is version control used for?","Track changes and collaborate on source code","Measure CPU temperature","Replace testing","Encrypt every database automatically","Version control records history and supports collaboration."),
("What is a unit test?","A test of a small isolated unit of behavior","A full production deployment","A database backup","A network cable test only","Unit tests focus on small components with controlled inputs."),
("What is debugging?","Finding and correcting defects in software","Adding random features","Deleting every test","Compressing network traffic","Debugging isolates the cause of incorrect behavior."),
("What does a compiler do?","Translate source code into another representation","Schedule student assignments","Route all network packets","Create database indexes automatically","Compilers translate programs and report many source-level errors."),
("What is an exception?","An event that interrupts normal program flow","A database table name","A CPU clock cycle","A user interface color","Exceptions communicate errors or unusual conditions."),
("What is authentication?","Verify the identity of a user or system","Determine permitted actions only","Compress an image","Sort a list","Authentication verifies identity; authorization determines permissions."),
("What is authorization?","Determine which actions an identity may perform","Verify a password only","Compile the application","Create a network cable","Authorization enforces access permissions after identity is established."),
("Why validate user input?","Reject malformed or unsafe data before processing","Guarantee all users are trusted","Remove the need for authentication","Increase duplicate records","Input validation protects correctness and reduces security risk."),
("What is a data structure?","A way to organize data for efficient operations","A deployment environment only","A password reset email","A physical keyboard","Data structures shape how data is stored and accessed."),
("What is an invariant in software?","A condition that should remain true at defined points","A random test value","A network outage","A UI animation","Invariants express properties code must preserve."),
("What is a database schema?","The defined structure of database objects and relationships","A CPU scheduling policy","A source control branch","A browser cookie only","Schemas describe tables, fields, constraints, and relationships."),
("What does scalability mean?","Ability to handle growth in workload or users","Ability to run only on one device","A guarantee of zero defects","A fixed screen size","Scalability describes handling increased demand."),
("What is a regression test?","A test that checks existing behavior after a change","A test that never runs again","A type of database index","A hardware sensor","Regression tests detect previously working behavior that broke after a change."),
],
}


def get_subject_questions(course_title: str, count: int = 15) -> list[dict]:
    """Return up to 15 unique multiple-choice questions matched to a course title."""
    title = str(course_title or "").casefold()
    if any(word in title for word in ("distributed", "backend", "microservice", "cloud computing")):
        subject, label = "distributed", "Distributed Systems and Backend Development"
    elif any(word in title for word in ("embedded", "iot", "internet of things", "microcontroller")):
        subject, label = "iot", "Embedded Systems and IoT"
    elif any(word in title for word in ("data structure", "algorithm", "dsa")):
        subject, label = "dsa", "Data Structures and Algorithms"
    elif any(word in title for word in ("machine learning", "artificial intelligence", "deep learning")) or title.strip() in {"ml", "ai"}:
        subject, label = "ml", "Machine Learning"
    elif any(word in title for word in ("operating system", "systems programming")) or title.strip() in {"os", "operating systems"}:
        subject, label = "os", "Operating Systems"
    elif any(word in title for word in ("database", "dbms", "sql", "relational")):
        subject, label = "dbms", "Database Management Systems"
    else:
        subject, label = "general", "Computer Science Fundamentals"
    limit = max(1, min(15, int(count)))
    questions = []
    for index, (prompt, answer, wrong1, wrong2, wrong3, explanation) in enumerate(BANKS[subject][:limit], start=1):
        options = [answer, wrong1, wrong2, wrong3]
        offset = (index * 3) % 4
        options = options[offset:] + options[:offset]
        questions.append({
            "id": index,
            "question": prompt,
            "context": f"Built-in subject question bank: {label}.",
            "options": options,
            "answer": answer,
            "source": f"{label} question bank",
            "question_type": "mcq",
            "max_marks": 1,
            "explanation": explanation,
        })
    return questions
