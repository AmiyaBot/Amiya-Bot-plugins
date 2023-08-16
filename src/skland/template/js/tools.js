function dateTime(time, format = 'y-m-d h:i:s') {
    const mSec = time * (time.toString().length < 13 ? 1000 : 1)
    const date = new Date(mSec)
    const zero = num => parseInt(num) < 10 ? '0' + num : num

    const contrast = {
        y: date.getFullYear(),
        m: zero(date.getMonth() + 1),
        d: zero(date.getDate()),
        h: zero(date.getHours()),
        i: zero(date.getMinutes()),
        s: zero(date.getSeconds())
    }

    for (let n in contrast) {
        format = format.replace(new RegExp(n, 'g'), contrast[n])
    }

    return format
}
