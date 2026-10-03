#include <algorithm>
#include <atomic>
#include <exception>
#include <condition_variable>
#include <memory>
#include <mutex>
#include <thread>

#include "common.h"

namespace tsc {

namespace {

class Pool {
public:
    explicit Pool(int n) : n_(std::max(1, n)) {
        for (int i = 1; i < n_; ++i) workers_.emplace_back([this, i] { loop(i); });
    }
    ~Pool() {
        {
            std::lock_guard<std::mutex> lk(m_);
            stop_ = true;
            ++gen_;
        }
        cv_.notify_all();
        for (auto& t : workers_) t.join();
    }
    int size() const { return n_; }

    // Runs task(tid) on all n_ threads (tid 0 = caller) and waits.
    void run(const std::function<void(int)>& task) {
        {
            std::lock_guard<std::mutex> lk(m_);
            task_ = &task;
            pending_ = n_ - 1;
            ++gen_;
        }
        cv_.notify_all();
        task(0);
        std::unique_lock<std::mutex> lk(m_);
        done_cv_.wait(lk, [this] { return pending_ == 0; });
        task_ = nullptr;
    }

private:
    void loop(int tid) {
        uint64_t seen = 0;
        for (;;) {
            const std::function<void(int)>* t;
            {
                std::unique_lock<std::mutex> lk(m_);
                cv_.wait(lk, [&] { return gen_ != seen; });
                seen = gen_;
                if (stop_) return;
                t = task_;
            }
            (*t)(tid);
            {
                std::lock_guard<std::mutex> lk(m_);
                if (--pending_ == 0) done_cv_.notify_one();
            }
        }
    }

    int n_;
    std::vector<std::thread> workers_;
    std::mutex m_;
    std::condition_variable cv_, done_cv_;
    const std::function<void(int)>* task_ = nullptr;
    int pending_ = 0;
    uint64_t gen_ = 0;
    bool stop_ = false;
};

thread_local int t_tid = -1;  // >= 0 while executing inside parallel_for

int g_threads = 0;
std::unique_ptr<Pool> g_pool;
std::mutex g_pool_mutex;

Pool& pool() {
    std::lock_guard<std::mutex> lk(g_pool_mutex);
    if (!g_pool) {
#ifdef TSC_SINGLE_THREAD  // build without threads (no SharedArrayBuffer needed in the browser)
        int n = 1;
#else
        int n = g_threads > 0 ? g_threads : (int)std::thread::hardware_concurrency();
#endif
        g_pool = std::make_unique<Pool>(std::max(1, n));
    }
    return *g_pool;
}

}  // namespace

int num_threads() { return pool().size(); }

void set_num_threads(int n) {
    std::lock_guard<std::mutex> lk(g_pool_mutex);
    g_threads = n;
    g_pool.reset();
}

void parallel_for(int64_t n, const std::function<void(int64_t, int64_t, int)>& fn, int64_t min_chunk) {
    if (n <= 0) return;
    if (t_tid >= 0) {  // nested call: run serially on the current thread
        fn(0, n, t_tid);
        return;
    }
    Pool& p = pool();
    int nt = p.size();
    if (nt == 1 || n <= min_chunk) {
        t_tid = 0;
        try {
            fn(0, n, 0);
        } catch (...) {
            t_tid = -1;
            throw;
        }
        t_tid = -1;
        return;
    }
    // dynamic scheduling in small chunks for load balance
    int64_t chunk = std::max<int64_t>(min_chunk, n / ((int64_t)nt * 4));
    if (chunk < 1) chunk = 1;
    std::atomic<int64_t> next{0};
    std::exception_ptr error;  // first exception of any thread; rethrown after all threads have finished
    std::mutex error_m;
    std::function<void(int)> task = [&](int tid) {
        t_tid = tid;
        try {
            for (;;) {
                int64_t b = next.fetch_add(chunk);
                if (b >= n) break;
                fn(b, std::min(n, b + chunk), tid);
            }
        } catch (...) {
            next.store(n);  // stop handing out work
            std::lock_guard<std::mutex> lk(error_m);
            if (!error) error = std::current_exception();
        }
        t_tid = -1;
    };
    p.run(task);
    if (error) std::rethrow_exception(error);
}

}  // namespace tsc
